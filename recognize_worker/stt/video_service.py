import subprocess
import os
import base64
import logging
from pathlib import Path

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
VISION_MODEL = os.getenv("VISION_MODEL", "moondream:1.8b")
FRAME_INTERVAL = int(os.getenv("FRAME_INTERVAL_SEC", "30"))  # секунд между кадрами
MAX_FRAMES = int(os.getenv("MAX_FRAMES", "20"))              # лимит кадров
SERVICE_NAME = "[VideoService]"


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

def extract_frames(video_path: str, output_dir: str) -> list[str]:
    """
    Извлекает ключевые кадры из видео с адаптивным интервалом.
    Количество кадров ограничено MAX_FRAMES.
    """
    os.makedirs(output_dir, exist_ok=True)

    duration = get_video_duration(video_path)

    if duration > 0:
        # Адаптируем интервал так, чтобы не превысить MAX_FRAMES
        interval = max(FRAME_INTERVAL, int(duration / MAX_FRAMES))
        logging.info(
            f"{SERVICE_NAME} Duration={duration:.0f}s, interval={interval}s, "
            f"expected_frames≈{int(duration / interval)}"
        )
    else:
        # Длительность неизвестна — используем FRAME_INTERVAL как есть,
        # лишние кадры срежем после извлечения
        interval = FRAME_INTERVAL
        logging.info(
            f"{SERVICE_NAME} Duration unknown, extracting with interval={interval}s"
        )

    output_pattern = os.path.join(output_dir, "frame_%04d.jpg")
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"fps=1/{interval},scale=1280:-2",
            "-q:v", "3",
            output_pattern,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logging.warning(
            f"{SERVICE_NAME} ffmpeg frame extraction returned code {result.returncode}:\n"
            f"{result.stderr[-500:] if result.stderr else ''}"
        )

    frames = sorted(
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.endswith(".jpg")
    )
    logging.info(f"{SERVICE_NAME} Extracted {len(frames)} frames")
    return frames[:MAX_FRAMES]


def _frame_to_base64(frame_path: str) -> str:
    with open(frame_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_frames(frames: list[str]) -> str:
    """
    Отправляет кадры во vision-модель Ollama и получает описание визуального контента встречи.
    Кадры группируются пакетами, чтобы не превышать лимит контекста модели.
    """
    if not frames:
        return ""

    logging.info(
        f"{SERVICE_NAME} Analyzing {len(frames)} frames "
        f"via '{VISION_MODEL}' at {OLLAMA_URL}"
    )

    BATCH_SIZE = 5  # кадров за один запрос к vision-модели
    all_descriptions: list[str] = []

    for batch_start in range(0, len(frames), BATCH_SIZE):
        batch = frames[batch_start: batch_start + BATCH_SIZE]
        images_b64 = [_frame_to_base64(f) for f in batch]

        frame_numbers = list(range(batch_start + 1, batch_start + len(batch) + 1))
        prompt = (
            f"Ты анализируешь кадры {frame_numbers[0]}–{frame_numbers[-1]} с записи рабочей встречи.\n"
            "Опиши что показано на экране"
        )

        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": VISION_MODEL,
                    "prompt": prompt,
                    "images": images_b64,
                    "stream": False,
                },
                timeout=300,
            )
            response.raise_for_status()
            description = response.json().get("response", "").strip()
            if description:
                all_descriptions.append(description)
        except Exception as exc:
            logging.warning(
                f"{SERVICE_NAME} Frame batch {batch_start}–{batch_start + len(batch)} "
                f"analysis failed: {exc}"
            )

    return "\n\n".join(all_descriptions)


def cleanup_frames(frames: list[str]):
    """Удаляет временные файлы кадров."""
    for f in frames:
        try:
            os.remove(f)
        except OSError:
            pass