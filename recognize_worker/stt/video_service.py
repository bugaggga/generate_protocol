import subprocess
import os
import base64
import logging
from pathlib import Path

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
VISION_MODEL = os.getenv("VISION_MODEL", "moondream:1.8b")
FRAME_INTERVAL = int(os.getenv("FRAME_INTERVAL_SEC", "30"))  # секунд между кадрами
MAX_FRAMES = int(os.getenv("MAX_FRAMES", "120"))              # лимит кадров
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


def get_video_duration(file_path: str) -> float:
    """
    Возвращает длительность видео в секундах.
    Три уровня fallback для надёжной работы с любыми контейнерами
    (в т.ч. записи экрана, OBS, незакрытые файлы без moov atom в начале).
    """

    def _parse(raw: str) -> float | None:
        v = raw.strip()
        if v and v != "N/A":
            try:
                return float(v)
            except ValueError:
                pass
        return None

    # 1) Длительность из контейнера (быстро, но бывает N/A или пусто)
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", file_path],
        capture_output=True, text=True,
    )
    if (d := _parse(r.stdout)) is not None:
        return d

    # 2) Длительность из видеопотока (помогает при отсутствии duration в заголовке)
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=duration", "-of", "csv=p=0", file_path],
        capture_output=True, text=True,
    )
    if (d := _parse(r.stdout)) is not None:
        return d

    # 3) Вычисляем из nb_frames / frame_rate (работает даже для «сырых» файлов)
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames,r_frame_rate",
         "-of", "csv=p=0", file_path],
        capture_output=True, text=True,
    )
    raw = r.stdout.strip()
    if raw and raw != "N/A":
        parts = raw.split(",")
        if len(parts) == 2:
            try:
                fps_parts = parts[0].split("/")
                fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else float(fps_parts[0])
                nb_frames = int(parts[1])
                return nb_frames / fps
            except (ValueError, ZeroDivisionError):
                pass

    logging.warning(f"{SERVICE_NAME} Could not determine video duration via ffprobe; "
                    f"will extract frames without interval adaptation")
    return 0.0

def extract_frames(video_path: str, output_dir: str) -> list[tuple[str, float]]:
    """
        Извлекает ключевые кадры из видео.
        Возвращает список пар (путь_к_файлу, временна́я_метка_в_секундах).
        Кадры сохраняются в output_dir и НЕ удаляются — они нужны llm_worker.
        """
    _require_file(video_path)
    os.makedirs(output_dir, exist_ok=True)

    duration = get_video_duration(video_path)
    if duration > 0:
        interval = max(FRAME_INTERVAL, int(duration / MAX_FRAMES))
        logging.info(f"{SERVICE_NAME} Duration={duration:.0f}s, interval={interval}s, "
                     f"expected≈{int(duration / interval)} frames")
    else:
        interval = FRAME_INTERVAL
        logging.info(f"{SERVICE_NAME} Duration unknown, interval={interval}s")

    output_pattern = os.path.join(output_dir, "frame_%04d.jpg")
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", video_path,
         "-vf", f"fps=1/{interval},scale=1280:-2", "-q:v", "3", output_pattern],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logging.warning(f"{SERVICE_NAME} ffmpeg extraction rc={result.returncode}: "
                        f"{result.stderr[-300:] if result.stderr else ''}")

    frame_files = sorted(f for f in os.listdir(output_dir) if f.endswith(".jpg"))

    # Временная метка для каждого кадра:
    # frame_0001.jpg → t=0, frame_0002.jpg → t=interval, ...
    frames_with_ts = [
        (os.path.join(output_dir, fname), i * interval)
        for i, fname in enumerate(frame_files)
    ]

    limited = frames_with_ts[:MAX_FRAMES]
    logging.info(f"{SERVICE_NAME} Extracted {len(limited)} frames with timestamps "
                 f"[0 .. {limited[-1][1] if limited else 0}s]")
    return limited


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