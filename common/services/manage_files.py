from pathlib import Path
import shutil
import os


TMP_DIR = os.getenv("TMP_DIR", "/worker/tmp")

def clean_operation_catalog(operation_id: str):
    folder = Path(f"{TMP_DIR}/{operation_id}")
    if folder.exists() and folder.is_dir():
        shutil.rmtree(folder)


