import logging
import tempfile
import os
import shutil
from pathlib import Path

from faster_whisper import WhisperModel

from common.services.s3_client import s3, BUCKET
from recognize_worker.stt.video_service import (
    is_video_file,
    extract_audio,
    extract_frames,
    analyze_frames,
    cleanup_frames,
)

logging.basicConfig(level=logging.INFO)
TMP_DIR = os.getenv("TMP_DIR", "/worker/tmp")
SERVICE_NAME="[Recognize]"
os.makedirs(TMP_DIR, exist_ok=True)

class RecognizeService:
    def __init__(self, model_path: str):
        logging.info(f"{SERVICE_NAME} Loading STT model...")

        self.model = WhisperModel(
            model_path,
            device="cpu",
            compute_type="int8"
        )

        logging.info(f"{SERVICE_NAME} STT Model loaded")

    def download_file(self, key: str, operation_id: str) -> str:
        logging.info(f"{SERVICE_NAME} Downloading file from {key}")

        folder_path = Path(f"{TMP_DIR}/{operation_id}")
        folder_path.mkdir(exist_ok=True)
        ext = os.path.splitext(key)[-1] or ""

        tmp_file = (tempfile.NamedTemporaryFile(
            delete=False,
            dir=folder_path,
            suffix=ext
        ))

        s3.download_file(BUCKET, key, tmp_file.name)

        return tmp_file.name

    def recognize(self, s3_key: str, operation_id: str) -> str:
        """
        Точка входа: скачивает файл из S3, определяет тип (аудио / видео)
        и возвращает обогащённый текстовый контекст для LLM.
        """
        temp_file_path = self.download_file(s3_key, operation_id)
        result = ""
        try:
            if is_video_file(temp_file_path):
                logging.info(f"{SERVICE_NAME} Detected VIDEO file, running full pipeline")
                result = self._transcribe_video(Path(temp_file_path))
            else:
                logging.info(f"{SERVICE_NAME} Detected AUDIO file, running STT only")
                result = self._transcribe_audio(temp_file_path)
        finally:
            try:
                os.remove(temp_file_path)
            except OSError:
                pass

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transcribe_audio(self, file_path: str) -> str:
        """Транскрибирует аудиофайл через Whisper и возвращает текст."""
        logging.info(f"{SERVICE_NAME} Start STT: {file_path}")

        segments, _ = self.model.transcribe(
            file_path,
            beam_size=5,
            vad_filter=True,
            word_timestamps=True,
            temperature=0.0,
        )

        full_text = " ".join(s.text for s in segments)
        logging.info(f"{SERVICE_NAME} STT done. Length={len(full_text)}")
        return full_text

    def _transcribe_video(self, tmp_video_path: Path) -> str:
        """
        Полный пайплайн для видеофайла:
            1. Извлечение аудио → Whisper
            2. Извлечение ключевых кадров → Vision LLM (Ollama)
            3. Объединение результатов в единый контекст
        """
        # --- Шаг 1: аудиодорожка → транскрипция ---
        tmp_audio_path = tmp_video_path.with_name("audio.wav")
        transcript = ""
        try:
            extract_audio(tmp_video_path, tmp_audio_path)
            transcript = self._transcribe_audio(str(tmp_audio_path))
        finally:
            try:
                os.remove(str(tmp_audio_path))
            except OSError:
                pass

        # --- Шаг 2: ключевые кадры → визуальный контекст ---
        frames_dir = f"{str(tmp_video_path.parent)}/frames"
        frames: list[str] = []
        visual_context = ""
        try:
            frames = extract_frames(str(tmp_video_path), frames_dir)
            visual_context = analyze_frames(frames)
        finally:
            cleanup_frames(frames)
            shutil.rmtree(frames_dir, ignore_errors=True)

        # --- Шаг 3: сборка итогового контекста ---
        return _combine_context(transcript, visual_context)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _combine_context(transcript: str, visual_context: str) -> str:
    """
    Объединяет речевую транскрипцию и визуальный контекст в единый текст
    для последующей обработки LLM-воркером.
    """
    parts: list[str] = []

    if visual_context.strip():
        parts.append(
            "=== ВИЗУАЛЬНЫЙ КОНТЕКСТ ВСТРЕЧИ ===\n"
            "(Описание слайдов, материалов и событий с видеозаписи)\n\n"
            + visual_context.strip()
        )

    if transcript.strip():
        parts.append(
            "=== ТРАНСКРИПЦИЯ РЕЧИ ===\n"
            + transcript.strip()
        )

    if not parts:
        logging.warning("[STT] Both transcript and visual context are empty")
        return ""

    return "\n\n" + "\n\n".join(parts) + "\n"