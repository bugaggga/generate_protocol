import logging
from datetime import datetime, timezone
from typing import Type

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from common.core.db import AsyncSessionLocal
from common.models.dto import ProcessingStatus

from common.models.orm_models import Operation, OperationVersion

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

async def is_version_active(version_id: str) -> bool:
    """
        Единственная функция проверки версии для всех воркеров.
        Один SELECT по PK — без сравнения int-полей, без чтения operations.
        """
    try:
        async with AsyncSessionLocal() as db:
            ver = await db.get(OperationVersion, version_id)
            return ver is not None and ver.is_active
    except Exception:
        logging.exception("[DB] Failed to check version")
        return False  # при ошибке остановка

async def deactivate_version(version_id: str) -> None:
    """ Деактивация конкретной версии """
    try:
        async with AsyncSessionLocal() as db:
            ver = await db.get(OperationVersion, version_id)
            if ver and ver.is_active:
                ver.is_active = False
                ver.deactivated_at = datetime.now(timezone.utc)
                await db.commit()
    except Exception:
        logging.exception("[DB] Failed to deactivate version")

async def maybe_mark_cancelled(operation_id: str) -> None:
    """
    Переводит операцию в cancelled если нет ни одной активной версии.
    Больше не опирается на статус 'cancelling'.
    """
    try:
        async with AsyncSessionLocal() as db:
            active = await db.scalar(
                select(OperationVersion)
                .filter_by(operation_id=operation_id, is_active=True)
            )
            if active:
                return  # кто-то уже запустил новую версию, пропустить

            operation = await db.get(Operation, operation_id)
            if operation and operation.status == ProcessingStatus.cancelling:
                operation.status = ProcessingStatus.cancelled
                await db.commit()
    except Exception:
        logging.exception("[DB] Failed to mark cancelled")

'''async def get_table_row(model: Type, row_id: uuid.UUID):
    async with AsyncSessionLocal() as db:
        row = await db.get(model, row_id)
        return row'''