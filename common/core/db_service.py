import logging

from sqlalchemy.ext.asyncio import AsyncSession
from common.core.db import AsyncSessionLocal

from common.models.orm_models import Operation


async def update_status(db: AsyncSession, operation_id: str, status: str):
    operation = await db.get(Operation, operation_id)

    '''if operation.status != "created":
        await message.ack()
        return'''

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