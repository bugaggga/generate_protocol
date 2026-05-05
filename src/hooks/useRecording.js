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
 
  const recorderRef  = useRef(null);
  const streamRef    = useRef(null);
  const chunksRef    = useRef([]);
  const timerRef     = useRef(null);
  //const resolveRef   = useRef(null); // резолвер промиса из start()
 
  // Чистим поток и таймер — вызывается и при stop, и при cancel
  const cleanup = useCallback(() => {
  clearInterval(timerRef.current);
  timerRef.current = null;

  const s = streamRef.current;
  if (s) {
    s.tabStream?.getTracks().forEach((t) => t.stop());
    s.micStream?.getTracks().forEach((t) => t.stop());
    s.audioCtx?.close();
    streamRef.current = null;
  }
}, []);
 
  const start = useCallback(async () => {
  setError(null);
  setRecState(REC_STATES.REQUESTING);

  // ── 1. Захват вкладки/системы ──────────────────────────────────────────
  let tabStream;
  try {
    tabStream = await navigator.mediaDevices.getDisplayMedia({
      video: true,   // браузер требует video:true, иначе отклоняет
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        sampleRate: 44100,
      },
    });
  } catch (err) {
    setRecState(REC_STATES.IDLE);
    setError(err.name === "NotAllowedError"
      ? "Захват экрана отменён."
      : err.message);
    throw err;
  }

  // Останавливаем видеодорожку — она нам не нужна
  tabStream.getVideoTracks().forEach((t) => t.stop());

  const tabAudioTracks = tabStream.getAudioTracks();
  if (tabAudioTracks.length === 0) {
    tabStream.getTracks().forEach((t) => t.stop());
    setRecState(REC_STATES.IDLE);
    const msg = 'Звук вкладки не захвачен. В диалоге выбора поставьте галочку "Поделиться звуком вкладки".';
    setError(msg);
    throw new Error(msg);
  }

  // ── 2. Захват микрофона (необязательно, но желательно) ─────────────────
  let micStream = null;
  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    // Микрофон недоступен — продолжаем только со звуком вкладки
    console.warn("[useRecording] Микрофон недоступен, пишем только вкладку");
  }

  // ── 3. Микшируем оба потока через AudioContext ─────────────────────────
  const audioCtx = new AudioContext();
  const destination = audioCtx.createMediaStreamDestination();

  audioCtx.createMediaStreamSource(tabStream).connect(destination);
  if (micStream) {
    audioCtx.createMediaStreamSource(micStream).connect(destination);
  }

  // Сохраняем ссылки для cleanup
  streamRef.current = { tabStream, micStream, audioCtx };

  // ── 4. Запускаем запись на смешанный поток ─────────────────────────────
  chunksRef.current = [];
  const recorder = new MediaRecorder(destination.stream);
  recorderRef.current = recorder;

  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunksRef.current.push(e.data);
  };

  const filePromise = new Promise((resolve, reject) => {
    recorder.onstop = () => {
      cleanup();
      const mimeType = recorder.mimeType || "audio/webm";
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

  recorder.start(500);
  setRecState(REC_STATES.RECORDING);
  setDuration(0);
  timerRef.current = setInterval(() => setDuration((d) => d + 1), 1000);

  return filePromise;
}, [cleanup]);
 
  const stop = useCallback(() => {
    if (recorderRef.current?.state === "recording") {
      setRecState(REC_STATES.STOPPING);
      recorderRef.current.stop(); // → onstop → resolve
    }
  }, []);
 
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