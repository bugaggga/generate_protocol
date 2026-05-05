import logging
import tempfile
import os

from faster_whisper import WhisperModel

from common.services.s3_client import s3, BUCKET

logging.basicConfig(level=logging.INFO)
TMP_DIR = os.getenv("TMP_DIR", "/worker/tmp")
SERVICE_NAME="[STT]"
os.makedirs(TMP_DIR, exist_ok=True)

class STTService:
    def __init__(self, model_path: str):
        logging.info(f"{SERVICE_NAME} Loading model...")

        self.model = WhisperModel(
            model_path,
            device="cpu",
            compute_type="int8"
        )

        logging.info(f"{SERVICE_NAME} Model loaded")

    def download_file(self, key: str) -> str:
        logging.info(f"{SERVICE_NAME} Downloading file from {key}")

        tmp_file = (tempfile.NamedTemporaryFile(
            delete=False,
            dir=TMP_DIR,
        ))

        s3.download_file(BUCKET, key, tmp_file.name)

        return tmp_file.name

    def transcribe(self, s3_key: str) -> str:
        file_path = self.download_file(s3_key)

        logging.info(f"{SERVICE_NAME} Start transcription: {file_path}")

        try:
            segments, info = self.model.transcribe(
                file_path,
                beam_size=5,
                vad_filter=True,
                word_timestamps=True,
                temperature=0.0,
            )

            full_text = " ".join([s.text for s in segments])

            logging.info(f"{SERVICE_NAME} Transcription done. Length={len(full_text)}")

            return full_text

        finally:
            os.remove(file_path)