import boto3
import os
from botocore.config import Config

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