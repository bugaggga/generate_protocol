from pathlib import Path
import logging
import os

TMP_DIR = os.getenv("TMP_DIR", "/worker/tmp")

def save_protocol(text: str, operation_id: str) -> str:
    path = Path(f"{TMP_DIR}/{operation_id}/protocol.txt")

    # Создаём директорию, если её нет (parents=True создаёт все родительские директории)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

    return str(path)

def read_file(file_path: str) -> str:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"[File] Not found: {file_path}")

    if not path.is_file():
        raise ValueError(f"[File] Not a file: {file_path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            return f.read()

    except UnicodeDecodeError:
        logging.warning(f"[File] UTF-8 decode failed, trying fallback: {file_path}")
        with path.open("r", encoding="cp1251") as f:
            return f.read()

    except Exception:
        logging.exception(f"[File] Failed to read file: {file_path}")
        raise