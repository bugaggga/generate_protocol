def save_protocol(text: str, operation_id: str) -> str:
    path = f"/worker/tmp/{operation_id}_protocol.txt"

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

    return path

import logging
from pathlib import Path


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