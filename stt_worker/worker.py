import json
import logging

from common.core.db_service import safe_update_status, get_status
from common.models.dto import ProcessingStatus
from common.services.queue import async_consume, publish
from stt_worker.stt.stt_service import STTService
import asyncio
import aio_pika

MAX_RETRIES = 3
RETRY_DELAY = 3  # сек
STT_QUEUE="stt_tasks"
TO_LLM_QUEUE="llm_tasks"
SERVICE_NAME="[STT Worker]"

logging.basicConfig(level=logging.INFO)

stt_service = STTService(model_path="models/stt")

async def process_stt(message: aio_pika.IncomingMessage):
    #async with message.process():  # автоматически ack/nack
    body = json.loads(message.body)
    operation_id = body["operation_id"]
    s3_key = body["file_s3_key"]

    logging.info(f"{SERVICE_NAME} Received task: {operation_id}")

    try:
        await message.ack()
    except Exception:
        logging.exception(f"{SERVICE_NAME} Failed to ACK message early")
        return

    try:
        status = await get_status(operation_id)
        if status == ProcessingStatus.partially_completed:
            return

        txt_file = await process_with_retry(operation_id, s3_key)

        # отправка в LLM очередь
        await publish_llm_task(operation_id, txt_file)

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
        stt_service.transcribe,
        s3_key
    )

    txt_file = save_to_txt(result, operation_id)

    await safe_update_status(operation_id, ProcessingStatus.partially_completed)

    return txt_file

async def publish_llm_task(operation_id: str, transcript_path: str):
    await publish(TO_LLM_QUEUE, {
        "operation_id": operation_id,
        "transcript_path": transcript_path
    })

def save_to_txt(text: str, operation_id: str) -> str:
    file_path = f"/worker/tmp/{operation_id}.txt"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)

    return file_path

async def main():
    logging.info(f"{SERVICE_NAME} Starting...")

    await async_consume(process_stt,STT_QUEUE,1)


if __name__ == "__main__":
    asyncio.run(main())