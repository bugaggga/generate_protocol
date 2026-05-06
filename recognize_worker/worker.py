import json
import logging
import os

from common.core.db_service import safe_update_status, get_status, is_version_active, \
    maybe_mark_cancelled
from common.models.dto import ProcessingStatus
from common.services.queue import async_consume, publish
from recognize_worker.stt.recognize_service import RecognizeService
import asyncio
import aio_pika
from common.services.s3_client import is_object_exists

MAX_RETRIES = 3
RETRY_DELAY = 3  # сек
RECOGNIZE_QUEUE="recognize_tasks"
TO_LLM_QUEUE="llm_tasks"
SERVICE_NAME="[Recognize Worker]"

logging.basicConfig(level=logging.INFO)

recognize_service = RecognizeService(model_path="models/stt")

async def process_stt(message: aio_pika.IncomingMessage):
    body = json.loads(message.body)
    operation_id = body["operation_id"]
    s3_key = body["file_s3_key"]
    version = body["version"]

    # Чекпоинт 1: до начала тяжёлой работы
    if not await is_version_active(operation_id, version):
        logging.info(f"{SERVICE_NAME} v{version} outdated, skipping")
        await message.ack()
        await maybe_mark_cancelled(operation_id)
        return

    status = await get_status(operation_id)
    if status == ProcessingStatus.partially_completed:
        await message.ack()
        return

    logging.info(f"{SERVICE_NAME} Received task: {operation_id}")

    # Файл есть в S3?
    if not is_object_exists(s3_key):
        logging.info(f"{SERVICE_NAME} Wait for object in s3...")
        await asyncio.sleep(8)
        await message.nack(requeue=True)
        return

    await message.ack()

    try:
        txt_file = await process_with_retry(operation_id, s3_key)

        # Чекпоинт 2: после транскрипции (может занять минуты)
        if not await is_version_active(operation_id, version):
            logging.info(f"{SERVICE_NAME} v{version} outdated after STT, stopping")
            await maybe_mark_cancelled(operation_id)
            return

        # отправка в LLM очередь
        await publish_llm_task(operation_id, txt_file, version)

        await safe_update_status(operation_id, ProcessingStatus.partially_completed)

    except Exception:
        logging.exception(f"{SERVICE_NAME} Failed")
        await safe_update_status(operation_id, ProcessingStatus.failed)

async def process_with_retry(operation_id: str, s3_key: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"{SERVICE_NAME} Attempt {attempt}/{MAX_RETRIES}")

            file_path = await process_pipeline(operation_id, s3_key)

            return  file_path # успех

        except Exception:
            logging.exception(f"{SERVICE_NAME} Attempt {attempt} failed")

            if attempt == MAX_RETRIES:
                raise

            await asyncio.sleep(RETRY_DELAY)

async def process_pipeline(operation_id: str, s3_key: str):
    await safe_update_status(operation_id, ProcessingStatus.processing)

    # STT
    result = await asyncio.to_thread(
        recognize_service.recognize,
        s3_key,
        operation_id
    )

    txt_file = save_to_txt(result, operation_id)

    return txt_file

async def publish_llm_task(operation_id: str, transcript_path: str, version: int):
    await publish(TO_LLM_QUEUE, {
        "operation_id": operation_id,
        "transcript_path": transcript_path,
        "version": version,
    })

def save_to_txt(text: str, operation_id: str) -> str:
    dir_path = f"/worker/tmp/{operation_id}"
    file_path = f"{dir_path}/transcription.txt"

    os.makedirs(dir_path, exist_ok=True)  # создаёт всю цепочку директорий

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)

    return file_path

async def main():
    logging.info(f"{SERVICE_NAME} Starting...")

    await async_consume(process_stt,RECOGNIZE_QUEUE,1)


if __name__ == "__main__":
    asyncio.run(main())