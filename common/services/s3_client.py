import boto3
import os
from botocore.config import Config
from botocore.exceptions import ClientError
import logging

BUCKET = os.getenv("AWS_S3_BUCKET")
SERVICE_NAME="[S3_Client]"

s3 = boto3.client(
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

def is_object_exists(key: str) -> bool:
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except s3.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise  # другие ошибки (403, 500...) пробрасываем дальше

def create_presigned_post(object_key, expiration=3600, fields=None):

    # = [["content-length-range", 1, max_size]]
    logging.info(f"{SERVICE_NAME} Creating presigned URL...")
    try:
        response = s3.generate_presigned_post(
            BUCKET,
            object_key,
            Fields=fields,
            #Conditions=conditions,
            ExpiresIn=expiration
        )
    except ClientError as e:
        logging.error(e)
        return None

    return response