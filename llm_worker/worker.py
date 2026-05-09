import json
import aio_pika
import asyncio
import logging

from common.core.db_service import safe_update_status, get_status, get_params, set_result, \
    is_version_active, maybe_mark_cancelled
from common.models.dto import ProcessingStatus
from common.services.queue import async_consume, publish
from llm_worker.llm.llm_service import build_protocol
from llm_worker.llm.manage_protocol import save_protocol, read_file

LLM_QUEUE="llm_tasks"
SERVICE_NAME="[LLM Worker]"

logging.basicConfig(level=logging.INFO)

async def process_llm(message: aio_pika.IncomingMessage):
    body = json.loads(message.body)
    operation_id = body["operation_id"]
    transcript_path = body["transcript_path"]
    frames_meta = body.get("frames_meta")
    version = body["version"]

    # Чекпоинт 1
    if not await is_version_active(operation_id, version):
        await message.ack()
        await maybe_mark_cancelled(operation_id)
        return

    try:
        await message.ack()  # early ack

        form = await get_params(operation_id)
        status = await get_status(operation_id)
        if status == ProcessingStatus.completed:
            return

        transcript = read_file(transcript_path)

        loop = asyncio.get_event_loop()  # берём loop до входа в поток

        json_protocol, md_protocol = await asyncio.to_thread(
            build_protocol,
            transcript,
            form,
            frames_meta,
            str(operation_id),
            version,
            loop,
        )

        json_folder = f"{operation_id}/json"
        logging.info(f"{SERVICE_NAME}: json_Protocol saved in {save_protocol(json_protocol, json_folder)}")
        logging.info(f"{SERVICE_NAME}: Protocol saved in {save_protocol(md_protocol, operation_id)}")

        logging.info(f"{SERVICE_NAME}: Setting result...")
        await set_result(json.loads(json_protocol), md_protocol, operation_id)
        await safe_update_status(operation_id, ProcessingStatus.completed)

    except asyncio.CancelledError:
        # Штатная отмена — не ошибка
        logging.info(f"{SERVICE_NAME} v{version} outdated during LLM, stopping")
        await maybe_mark_cancelled(operation_id)

    except Exception:
        # отправка в LLM очередь
        #await publish_llm_task(operation_id, transcript_path)

        logging.exception(f"{SERVICE_NAME} Failed")
        await safe_update_status(operation_id, ProcessingStatus.failed)


async def publish_llm_task(operation_id: str, transcript_path: str):
    await publish(LLM_QUEUE, {
        "operation_id": operation_id,
        "transcript_path": transcript_path
    })

async def main():
    logging.info(f"{SERVICE_NAME} Starting...")

    await async_consume(process_llm, LLM_QUEUE, 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info(f"{SERVICE_NAME} Stopped")