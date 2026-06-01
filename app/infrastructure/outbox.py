import logging
import asyncio
from common.models.orm_models import RecognizeTask, LlmTask
from sqlalchemy import select
from common.core.db import AsyncSessionLocal
from common.models.orm_models import BaseTask
from common.services.queue import publish
from common.models.dto import TaskStatus

from sqlalchemy.exc import OperationalError, InterfaceError, DBAPIError

POLL_INTERVAL = 1  # сек
SERVICE_NAME = "[OutBox]"

# Таблица → (модель, имя очереди, имя id-поля в сообщении)
OUTBOX_CONFIG = [
    (RecognizeTask, "recognize_tasks", "recognize_task_id"),
    (LlmTask,       "llm_tasks",       "llm_task_id"),
]

async def outbox_loop():
    backoff = 1
    while True:
        try:
            for model, queue_name, id_field in OUTBOX_CONFIG:
                await outbox_table(model, queue_name, id_field)
            backoff = 1  # сброс после успешной итерации
            await asyncio.sleep(POLL_INTERVAL)
        except asyncio.CancelledError:
            raise
        except (OperationalError, InterfaceError, DBAPIError, OSError) as e:
            logging.warning(f"[OutBox] инфраструктура недоступна ({e.__class__.__name__}), повтор через {backoff}с")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)  # 1→2→4…→30с, не чаще
        except Exception:
            logging.exception("[OutBox] неожиданная ошибка")  # только настоящие баги с трейсбеком
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
                })
                row.status = TaskStatus.queued
            if rows:
                logging.info(f"{SERVICE_NAME} {queue_name}: published {len(rows)}")