import subprocess
import os
import base64
import logging
from pathlib import Path
import cv2
import numpy as np

FRAME_INTERVAL = int(os.getenv("FRAME_INTERVAL_SEC", "30"))  # секунд между кадрами
SCENE_THRESHOLD = 30.0  # чувствительность scene detection (20–40)
#MAX_FRAMES = int(os.getenv("MAX_FRAMES", "120"))              # лимит кадров
SERVICE_NAME = "[VideoService]"

def _require_file(path: str) -> None:
    if not os.path.exists(path):
        raise Exception(
            f"Operation file was removed during processing: {path}"
        )

def is_video_file(file_path: str) -> bool:
    """Проверяет наличие видеодорожки в файле через ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            file_path,
        ],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == "video"


def extract_audio(video_path: Path, output_path: Path) -> str:
    """Извлекает аудиодорожку из видео в WAV 16kHz mono (формат для Whisper)."""
    logging.info(f"{SERVICE_NAME} Extracting audio from video → {str(output_path)}")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(output_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return str(output_path)


def resize_for_vl_model(frame, patch_size=28, max_width=448):
    h, w = frame.shape[:2]

    # масштабируем по ширине
    scale = max_width / w
    new_w = max_width
    new_h = int(h * scale)

    # округляем высоту до кратного patch_size
    new_h = (new_h // patch_size) * patch_size

    return cv2.resize(frame, (new_w, new_h))

def extract_frames(video_path: str, output_dir: str) -> list[tuple[str, float]]:
    """
        Извлекает ключевые кадры из видео.
        Возвращает список пар (путь_к_файлу, временна́я_метка_в_секундах).
        Кадры сохраняются в output_dir и НЕ удаляются — они нужны llm_worker.
        """
    _require_file(video_path)
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps

    # fallback-интервал в кадрах (не реже чем раз в N секунд)
    fallback_interval_sec = FRAME_INTERVAL
    fallback_interval_frames = int(fallback_interval_sec * fps)

    logging.info(
        f"{SERVICE_NAME} Duration={duration:.0f}s, fps={fps:.1f}, "
        f"fallback_interval={fallback_interval_sec}s"
    )

    selected = []  # (frame_idx, timestamp, frame)
    prev_gray = None
    last_captured_idx = -fallback_interval_frames
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frames_since_last = frame_idx - last_captured_idx

        should_capture = False

        if prev_gray is not None:
            diff = np.mean(cv2.absdiff(gray, prev_gray))
            if diff > SCENE_THRESHOLD:
                should_capture = True

        if frames_since_last >= fallback_interval_frames:
            should_capture = True

        if should_capture:
            timestamp = frame_idx / fps  # ← вот и метка
            selected.append((frame_idx, timestamp, frame.copy()))
            last_captured_idx = frame_idx

        prev_gray = gray
        frame_idx += 1

    cap.release()

    # Сохранение и масштабирование
    frames_with_ts = []
    for i, (frame_idx, timestamp, frame) in enumerate(selected):
        fname = f"frame_{i + 1:04d}.jpg"
        fpath = os.path.join(output_dir, fname)
        frame = resize_for_vl_model(frame)

        cv2.imwrite(fpath, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        frames_with_ts.append((fpath, timestamp))

    logging.info(
        f"{SERVICE_NAME} Extracted {len(frames_with_ts)} frames, "
        f"timestamps: {[round(ts, 1) for _, ts in frames_with_ts]}"
    )

    return frames_with_ts


def _encode_frame_b64(path: str) -> str | None:
    """Читает .jpg и возвращает base64-строку. None при ошибке чтения."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except OSError as e:
        logging.warning(f"{SERVICE_NAME} Cannot read frame {path}: {e}")
        return None


def cleanup_frames(frames: list[str]):
    """Удаляет временные файлы кадров."""
    for f in frames:
        try:
            os.remove(f)
        except OSError:
            pass