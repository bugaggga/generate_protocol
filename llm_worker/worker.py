import json
import aio_pika
import asyncio
import logging

from common.core.db import AsyncSessionLocal
from common.core.db_service import is_version_active, maybe_mark_cancelled
from common.models.dto import TaskStatus
from common.models.orm_models import LlmTask
from common.services.queue import async_consume
from common.services.s3_client import upload_protocol, load_frames_from_s3, get_file
from llm_worker.llm.llm_service import build_protocol

LLM_QUEUE="llm_tasks"
SERVICE_NAME="[LLM Worker]"

logging.basicConfig(level=logging.INFO)

async def process_llm(message: aio_pika.IncomingMessage):
    body = json.loads(message.body)
    llm_task_id = body["id"]

    llm_task = await get_task(llm_task_id,
                              message)
    if not llm_task: return
    operation_id = llm_task.operation_id
    version_id = llm_task.version_id

    # Проверка №1
    if not await is_version_active(version_id):
        await message.ack()
        await maybe_mark_cancelled(operation_id)
        return

    await message.ack()  # early ack

    try:
        frames_meta = load_frames_from_s3(key=llm_task.frames_key)
        transcript = get_file(llm_task.transcript_s3_key)
        #transcript_path = f"/worker/tmp/{operation_id}/transcription.txt"
        #download_file(llm_task.transcript_s3_key, transcript_path)
        #transcript = read_file(transcript_path)


        loop = asyncio.get_event_loop()  # берём loop до входа в поток

        json_protocol, md_protocol = await asyncio.to_thread(
            build_protocol,
            transcript,
            llm_task.params,
            frames_meta,
            str(operation_id),
            version_id,
            loop,
        )
        json_str = json.dumps(json_protocol, ensure_ascii=False, indent=2)

        # Результат — в S3
        await asyncio.to_thread(
            upload_protocol,
            json_str, md_protocol, operation_id, version_id
        )

        # 2. Обновление статуса
        async with AsyncSessionLocal() as db:
            llm_task = await db.get(LlmTask, llm_task_id)
            llm_task.status = TaskStatus.done
            await db.commit()

        logging.info(f"{SERVICE_NAME}: Setting result...")

    except asyncio.CancelledError:
        # Штатная отмена — не ошибка
        logging.info(f"{SERVICE_NAME} v{version_id} outdated during LLM, stopping")
        await maybe_mark_cancelled(operation_id)

    except Exception:
        logging.exception(f"{SERVICE_NAME} Failed")
        async with AsyncSessionLocal() as db:  # ← только своя таблица
            task = await db.get(LlmTask, llm_task_id)
            task.status = TaskStatus.failed
            await db.commit()

async def get_task(task_id, message: aio_pika.IncomingMessage) ->  LlmTask | None:
    async with AsyncSessionLocal() as db:
        # Получение задачи на генерацию
        task = await db.get(LlmTask, task_id)
        if not task or task.status != TaskStatus.queued:
            await message.ack()
            return
        task.status = TaskStatus.processing

        await db.commit()
        return task

async def main():
    logging.info(f"{SERVICE_NAME} Starting...")

    await async_consume(process_llm, LLM_QUEUE, 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info(f"{SERVICE_NAME} Stopped")