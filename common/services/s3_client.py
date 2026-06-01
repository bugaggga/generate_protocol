from io import BytesIO

import boto3
import os
from botocore.config import Config
from botocore.exceptions import ClientError
import logging
import json

AWS_BUCKET = os.getenv("AWS_S3_BUCKET")
MINIO_BUCKET = os.getenv("MINIO_S3_BUCKET")
SERVICE_NAME="[S3_Client]"

_internal_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT_URL", "http://minio:9000"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("S3_REGION", "us-east-1"),
    config=Config(
        signature_version="s3v4",
        retries={"max_attempts": 3},
        connect_timeout=5,
        read_timeout=120,
    )
)

# Внешний клиент — для генерации presigned URL, доступных из браузера
_public_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_PUBLIC_URL", "http://localhost:9000"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin"),
    region_name=os.getenv("S3_REGION", "us-east-1"),
    config=Config(signature_version="s3v4"),
)

def download_file(key: str, dest_path: str):
    """Скачивает файл внутри Docker-сети."""
    _internal_client.download_file(MINIO_BUCKET, key, dest_path)

def get_file(key: str):
    response = _internal_client.get_object(Bucket=MINIO_BUCKET, Key=key)
    content = response["Body"].read().decode("utf-8")
    return content

def delete_object(key: str):
    _internal_client.delete_object(Bucket=MINIO_BUCKET, Key=key)

def write_file(text: str, key: str):
    _internal_client.upload_fileobj(
        BytesIO(text.encode('utf-8')),
        MINIO_BUCKET,
        Key=key)

def save_frames_to_s3(frames_meta: list[dict], key: str) -> None:
    lines = "\n".join(json.dumps(frame, ensure_ascii=False) for frame in frames_meta)

    _internal_client.put_object(
        Bucket=MINIO_BUCKET,
        Key=key,
        Body=lines.encode("utf-8"),
        ContentType="application/x-ndjson",
    )

def load_frames_from_s3(key: str) -> list[dict] | None:
    if not key:
        return

    content = get_file(key)
    return [json.loads(line) for line in content.splitlines() if line.strip()]

def is_object_exists(key: str) -> bool:
    try:
        _internal_client.head_object(Bucket=MINIO_BUCKET, Key=key)
        return True
    except _internal_client.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise  # другие ошибки (403, 500...) пробрасываем дальше

def create_presigned_post(object_key, expiration=3600, fields=None):
    logging.info(f"{SERVICE_NAME} Creating presigned URL...")
    try:
        response = _public_client.generate_presigned_post(
            MINIO_BUCKET,
            Key=object_key,
            Fields=fields,
            ExpiresIn=expiration
        )
    except ClientError as e:
        logging.error(e)
        return None

    return response


# ---- Обработка результатов ---- #

def upload_protocol(json_str: str, md_str: str,
                    operation_id: str, version_id: str) -> str:
    """Загружает оба файла протокола в S3. Возвращает базовый ключ."""
    base_key = f"operations/{operation_id}/{version_id}"

    _internal_client.put_object(
        Bucket=MINIO_BUCKET,
        Key=f"{base_key}/protocol.json",
        Body=json_str.encode(),
        ContentType="application/json",
    )
    _internal_client.put_object(
        Bucket=MINIO_BUCKET,
        Key=f"{base_key}/protocol.md",
        Body=md_str.encode(),
        ContentType="text/markdown",
    )
    return base_key


def download_protocol(operation_id: str, version_id: str) -> tuple[str, str]:
    """Скачивает json + md из S3. Бросает исключение если нет объекта."""
    base_key = f"operations/{operation_id}/{version_id}"

    json_obj = _internal_client.get_object(Bucket=MINIO_BUCKET,
                                            Key=f"{base_key}/protocol.json")
    md_obj   = _internal_client.get_object(Bucket=MINIO_BUCKET,
                                            Key=f"{base_key}/protocol.md")

    return json_obj["Body"].read().decode(), md_obj["Body"].read().decode()


# Удаление всех файлов операции

def delete_prefix(prefix: str) -> int:
    """
    Удаляет все объекты с заданным префиксом.
    Возвращает количество удалённых объектов.
    """
    paginator = _internal_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=MINIO_BUCKET, Prefix=prefix)

    deleted_count = 0
    for page in pages:
        objects = page.get("Contents", [])
        if not objects:
            continue

        delete_payload = {"Objects": [{"Key": obj["Key"]} for obj in objects]}
        response = _internal_client.delete_objects(
            Bucket=MINIO_BUCKET,
            Delete=delete_payload,
        )

        errors = response.get("Errors", [])
        if errors:
            logging.error(f"{SERVICE_NAME} Errors while deleting prefix '{prefix}': {errors}")
            raise ClientError(
                {"Error": {"Code": errors[0]["Code"], "Message": errors[0]["Message"]}},
                "DeleteObjects",
            )

        deleted_count += len(response.get("Deleted", []))

    logging.info(f"{SERVICE_NAME} Deleted {deleted_count} objects under prefix '{prefix}'")
    return deleted_count


def delete_operation_files(operation_id: str) -> int:
    """Удаляет все файлы операции из S3."""
    prefix = f"operations/{operation_id}/"
    return delete_prefix(prefix)