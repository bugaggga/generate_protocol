import { useState, useRef, useCallback } from "react";
 
export const REC_STATES = {
  IDLE:       "idle",
  REQUESTING: "requesting",  // ждём разрешение от браузера
  RECORDING:  "recording",   // идёт запись
  STOPPING:   "stopping",    // нажат стоп, финализируем chunks
};
 
function buildFilename(mimeType) {
  const ext = mimeType.includes("ogg") ? "ogg"
            : mimeType.includes("mp4") ? "mp4"
            : "webm";
  const ts = new Date().toISOString().slice(0, 19).replace("T", "_").replace(/:/g, "-");
  return `recording_${ts}.${ext}`;
}
 
/**
 * Хук управляет жизненным циклом MediaRecorder.
 *
 * Использование:
 *   const { recState, duration, error, start, stop, cancel } = useRecording();
 *
 *   start() → Promise<File>  — запрашивает микрофон, начинает запись.
 *                              Промис резолвится готовым File когда вызван stop().
 *   stop()                   — останавливает запись, резолвит промис из start().
 *   cancel()                 — отменяет запись без создания файла.
 */
export function useRecording() {
  const [recState, setRecState] = useState(REC_STATES.IDLE);
  const [duration, setDuration] = useState(0);
  const [error,    setError]    = useState(null);
 
  const recorderRef = useRef(null);
  const streamsRef  = useRef(null); // { tabStream, micStream, audioCtx }
  const chunksRef   = useRef([]);
  const timerRef    = useRef(null);
 
  // Освобождаем все треки и AudioContext
  const cleanup = useCallback(() => {
    clearInterval(timerRef.current);
    timerRef.current = null;
 
    const s = streamsRef.current;
    if (s) {
      s.tabStream?.getTracks().forEach((t) => t.stop());
      s.micStream?.getTracks().forEach((t) => t.stop());
      s.audioCtx?.close();
      streamsRef.current = null;
    }
  }, []);

  const stop = useCallback(() => {
    if (recorderRef.current?.state === "recording") {
      setRecState(REC_STATES.STOPPING);
      recorderRef.current.stop(); // → onstop → resolve
    }
  }, []);
 
  const start = useCallback(async () => {
    setError(null);
    setRecState(REC_STATES.REQUESTING);
 
    // ── 1. Захват экрана / вкладки ──────────────────────────────────────────
    let tabStream;
    try {
      tabStream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          frameRate: { ideal: 30 },
          displaySurface: "browser", // браузер предложит вкладки первыми
        },
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          sampleRate: 44100,
        },
      });
    } catch (err) {
      setRecState(REC_STATES.IDLE);
      const msg = err.name === "NotAllowedError"
        ? "Захват экрана отменён."
        : `Ошибка захвата экрана: ${err.message}`;
      setError(msg);
      throw new Error(msg);
    }
 
    const tabAudioTracks = tabStream.getAudioTracks();
    if (tabAudioTracks.length === 0) {
      tabStream.getTracks().forEach((t) => t.stop());
      setRecState(REC_STATES.IDLE);
      const msg = 'Звук вкладки не захвачен. В диалоге выбора поставьте галочку "Поделиться звуком вкладки".';
      setError(msg);
      throw new Error(msg);
    }
 
    // ── 2. Захват микрофона (необязательно) ─────────────────────────────────
    let micStream = null;
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      console.warn("[useRecording] Микрофон недоступен — пишем только звук вкладки");
    }
 
    // ── 3. Микшируем аудио-дорожки через AudioContext ───────────────────────
    const audioCtx    = new AudioContext();
    const destination = audioCtx.createMediaStreamDestination();
 
    audioCtx.createMediaStreamSource(tabStream).connect(destination);
    if (micStream) {
      audioCtx.createMediaStreamSource(micStream).connect(destination);
    }
 
    streamsRef.current = { tabStream, micStream, audioCtx };
 
    // ── 4. Собираем финальный поток: видео вкладки + смешанное аудио ────────
    const combinedStream = new MediaStream([
      ...tabStream.getVideoTracks(),
      ...destination.stream.getAudioTracks(),
    ]);
 
    // ── 5. Запускаем MediaRecorder ───────────────────────────────────────────
    chunksRef.current = [];
    const recorder = new MediaRecorder(combinedStream);
    recorderRef.current = recorder;
 
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
 
    // Промис резолвится через onstop (не async-executor — нет ESLint-предупреждения)
    const filePromise = new Promise((resolve, reject) => {
      recorder.onstop = () => {
        cleanup();
        const mimeType = recorder.mimeType || "video/webm";
        const blob = new Blob(chunksRef.current, { type: mimeType });
        const file = new File([blob], buildFilename(mimeType), { type: mimeType });
        setRecState(REC_STATES.IDLE);
        setDuration(0);
        resolve(file);
      };
 
      recorder.onerror = (e) => {
        cleanup();
        setRecState(REC_STATES.IDLE);
        const msg = e.error?.message ?? "Ошибка записи";
        setError(msg);
        reject(new Error(msg));
      };
    });
 
    // Пользователь закрыл шторку демонстрации — останавливаем запись
    tabStream.getVideoTracks()[0].onended = () => stop();
 
    recorder.start(500);
    setRecState(REC_STATES.RECORDING);
    setDuration(0);
    timerRef.current = setInterval(() => setDuration((d) => d + 1), 1000);
 
    return filePromise;
  }, [cleanup, stop]);
 
  const cancel = useCallback(() => {
    if (recorderRef.current) {
      recorderRef.current.onstop = null; // не резолвим промис
      if (recorderRef.current.state === "recording") {
        recorderRef.current.stop();
      }
    }
    cleanup();
    chunksRef.current = [];
    setRecState(REC_STATES.IDLE);
    setDuration(0);
    setError(null);
  }, [cleanup]);
 
  return { recState, duration, error, start, stop, cancel, REC_STATES };
}