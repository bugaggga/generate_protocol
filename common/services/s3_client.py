import boto3
import os
from botocore.config import Config
from botocore.exceptions import ClientError
import logging

AWS_BUCKET = os.getenv("AWS_S3_BUCKET")
MINIO_BUCKET = os.getenv("MINIO_S3_BUCKET")
SERVICE_NAME="[S3_Client]"

_internal_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("AWS_S3_ENDPOINT"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    config=Config(
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

def download_file(key: str, dest_path: str) -> None:
    """Скачивает файл внутри Docker-сети."""
    _internal_client.download_file(MINIO_BUCKET, key, dest_path)

def delete_object(key: str):
    _internal_client.delete_object(Bucket=MINIO_BUCKET, Key=key)

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