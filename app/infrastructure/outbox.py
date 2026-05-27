import logging
import asyncio
from common.models.orm_models import RecognizeTask, LlmTask
from sqlalchemy import select
from common.core.db import AsyncSessionLocal
from common.models.orm_models import BaseTask
from common.services.queue import publish
from common.models.dto import TaskStatus

POLL_INTERVAL = 1  # сек
SERVICE_NAME = "[OutBox]"

# Таблица → (модель, имя очереди, имя id-поля в сообщении)
OUTBOX_CONFIG = [
    (RecognizeTask, "recognize_tasks", "recognize_task_id"),
    (LlmTask,       "llm_tasks",       "llm_task_id"),
]

async def outbox_loop():
    while True:
        try:
            for model, queue_name, id_field in OUTBOX_CONFIG:
                await outbox_table(model, queue_name, id_field)
        except Exception:
            logging.exception(f"{SERVICE_NAME} iteration failed")
        await asyncio.sleep(POLL_INTERVAL)

async def outbox_table(table_model: BaseTask, queue_name: str, id_field: str, batch: int = 50):
    """
    Выбирает pending-записи одной таблицы, публикует в её очередь,
    переводит в queued. Публикация и смена статуса — в одной транзакции.
    """
    async with AsyncSessionLocal() as db:
        async with db.begin():
            rows = (await db.execute(
                select(table_model)
                .filter_by(status=TaskStatus.pending)
                .order_by(table_model.created_at)
                .with_for_update(skip_locked=True)   # защита от двойной публикации
                .limit(batch)
            )).scalars().all()

            for row in rows:
                await publish(queue_name, {
                    "id": str(row.id),               # recognize_task_id / llm_task_id
                    "version_id": str(row.version_id),
                    "operation_id": str(row.operation_id),
                })
                row.status = TaskStatus.queued
            if rows:
                logging.info(f"{SERVICE_NAME} {queue_name}: published {len(rows)}")