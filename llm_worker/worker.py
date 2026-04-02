import json
import aio_pika
import asyncio
import logging

from common.core.db_service import safe_update_status, get_status
from common.models.dto import ProcessingStatus
from common.services.queue import async_consume
from llm_worker.llm.llm_service import build_protocol
from llm_worker.llm.manage_protocol import save_protocol, read_file

LLM_QUEUE="llm_tasks"
SERVICE_NAME="[LLM Worker]"

logging.basicConfig(level=logging.INFO)

async def process_llm(message: aio_pika.IncomingMessage):
    body = json.loads(message.body)
    operation_id = body["operation_id"]
    transcript_path = body["transcript_path"]

    await message.ack()  # early ack

    try:
        status = await get_status(operation_id)
        if status == ProcessingStatus.completed:
            return

        transcript = read_file(transcript_path)

        protocol = await asyncio.to_thread(
            build_protocol,
            transcript
        )

        save_protocol(protocol, operation_id)

        await safe_update_status(operation_id, ProcessingStatus.completed)

    except Exception:
        logging.exception(f"{SERVICE_NAME} Failed")
        await safe_update_status(operation_id, ProcessingStatus.failed)

async def main():
    logging.info(f"{SERVICE_NAME} Starting...")

    await async_consume(process_llm, LLM_QUEUE, 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info(f"{SERVICE_NAME} Stopped")