import logging

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from common.core.db import AsyncSessionLocal
from common.models.dto import ProcessingStatus

from common.models.orm_models import Operation


async def update_status(db: AsyncSession, operation_id: str, status: str):
    operation = await db.get(Operation, operation_id)

    if not operation:
        raise ValueError(f"Operation {operation_id} not found")

    operation.status = status

async def safe_update_status(operation_id, status):
    try:
        async with AsyncSessionLocal() as db:
            await update_status(db, operation_id, status)
            await db.commit()
    except Exception:
        logging.exception("[DB] Failed to update status")

async def get_status(operation_id):
    try:
        async with AsyncSessionLocal() as db:
            operation = await db.get(Operation, operation_id)
            return operation.status
    except Exception:
        logging.exception("[DB] Failed to get status")

async def get_params(operation_id):
    try:
        async with AsyncSessionLocal() as db:
            operation = await db.get(Operation, operation_id)
            if not operation:
                return None
            return operation.params
    except Exception:
        logging.exception("[DB] Failed to get status")

async def set_result(json_value, md_value, operation_id):
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Operation)
                .where(Operation.id == operation_id)
                .values(json_res=json_value,
                        md_res=md_value)
            )

            await db.commit()
    except Exception:
        logging.exception("[DB] Failed to set result")

async def is_cancelled(operation_id: str) -> bool:
    """Проверяет, запрошена ли отмена операции."""
    try:
        async with AsyncSessionLocal() as db:
            operation = await db.get(Operation, str(operation_id))
            if not operation:
                return False
            return operation.status in (
                ProcessingStatus.cancelling,
                ProcessingStatus.cancelled,
            )
    except Exception:
        logging.exception("[DB] Failed to check cancellation")
        return False  # в случае ошибки не прерываем обработку

async def is_version_active(operation_id: str, version: int) -> bool:
    """
    Возвращает True, только если version == active_version в БД.
    Все остальные случаи (отмена, новый запуск, ошибка БД) → False.
    """
    try:
        async with AsyncSessionLocal() as db:
            op = await db.get(Operation, operation_id)
            if not op or op.status == ProcessingStatus.closed:
                return False
            return op.active_version == version
    except Exception:
        logging.exception("[DB] Failed to check version")
        return False  # безопаснее остановиться, чем продолжить

async def maybe_mark_cancelled(operation_id: str):
    """Ставим cancelled только если статус всё ещё cancelling (не перезапущено)."""
    status = await get_status(operation_id)
    if status == ProcessingStatus.cancelling:
        await safe_update_status(operation_id, ProcessingStatus.cancelled)