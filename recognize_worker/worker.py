import json
import logging
import os

from common.core.db import AsyncSessionLocal
from common.core.db_service import safe_update_status, is_version_active, \
    maybe_mark_cancelled, deactivate_version
from common.models.dto import ProcessingStatus, TaskStatus
from common.models.orm_models import RecognizeTask, LlmTask
from common.services.queue import async_consume
from recognize_worker.stt.recognize_service import RecognizeService
import asyncio
import aio_pika
from common.services.s3_client import write_file, save_frames_to_s3

MAX_RETRIES = 3
RETRY_DELAY = 3  # сек
RECOGNIZE_QUEUE="recognize_tasks"
TO_LLM_QUEUE="llm_tasks"
SERVICE_NAME="[Recognize Worker]"

logging.basicConfig(level=logging.INFO)

recognize_service = RecognizeService(model_path="models/stt")

async def process_stt(message: aio_pika.IncomingMessage):
    body = json.loads(message.body)
    rec_task_id = body["id"]  # ← только id

    rec_task = await get_task(rec_task_id)
    if not rec_task:
        await message.ack()
        return
    operation_id = rec_task.operation_id
    version_id = rec_task.version_id

    # Проверка №1
    if not await is_version_active(version_id):
        await message.ack()
        await maybe_mark_cancelled(operation_id)
        return

    logging.info(f"{SERVICE_NAME} Received task: {rec_task_id}")

    await message.ack()

    try:
        transcript_key, frames_key = await process_with_retry(operation_id, rec_task.file_s3_key)

        # Проверка №2
        if not await is_version_active(version_id):
            logging.info(f"{SERVICE_NAME} v{version_id} outdated after STT, stopping")
            await deactivate_version(version_id)  # уже деактивирована, но для явности
            await maybe_mark_cancelled(operation_id)
            return

        async with AsyncSessionLocal() as db:
            rec_task = await db.get(RecognizeTask, rec_task_id)
            # Создание задачи на генерацию
            llm_task = LlmTask(
                operation_id=operation_id,
                version_id=version_id,
                transcript_s3_key=transcript_key,
                frames_key=frames_key,
                status=TaskStatus.pending
            )
            db.add(llm_task)
            rec_task.status = TaskStatus.done
            await db.commit()

    except Exception:
        logging.exception(f"{SERVICE_NAME} Failed")
        async with AsyncSessionLocal() as db:  # ← только своя таблица
            task = await db.get(RecognizeTask, rec_task_id)
            task.status = TaskStatus.failed
            await db.commit()

async def get_task(task_id) -> RecognizeTask | None:
    async with AsyncSessionLocal() as db:
        # Получение задачи на генерацию
        task = await db.get(RecognizeTask, task_id)
        if not task or task.status != TaskStatus.queued:
            return
        task.status = TaskStatus.processing

        await db.commit()
        return task

async def process_with_retry(operation_id: str, s3_key: str) -> tuple[str, str | None]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"{SERVICE_NAME} Attempt {attempt}/{MAX_RETRIES}")

            transcript_key, frames_key = await process_pipeline(operation_id, s3_key)

            return  transcript_key, frames_key # успех

        except Exception:
            logging.exception(f"{SERVICE_NAME} Attempt {attempt} failed")

            if attempt == MAX_RETRIES:
                raise

            await asyncio.sleep(RETRY_DELAY)

async def process_pipeline(operation_id: str, s3_key: str) -> tuple[str, str | None]:
    await safe_update_status(operation_id, ProcessingStatus.processing)

    # STT
    transcript, frames_meta = await asyncio.to_thread(
        recognize_service.recognize,
        s3_key,
        operation_id
    )

    frames_key = None
    if frames_meta:
        frames_key = f"operations/{operation_id}/frames.jsonl"
        save_frames_to_s3(frames_meta, key=frames_key)
    transcript_key = f"operations/{operation_id}/transcript.txt"
    write_file(transcript, transcript_key)
    save_to_txt(transcript, operation_id)

    return transcript_key, frames_key

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