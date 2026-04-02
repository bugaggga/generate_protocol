from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from common.core.db import get_db
from common.models.orm_models import Operation

from common.models.dto import (
    ProcessingParamsDTO,
    SessionCreateResponseDTO, ProcessingStatus, AudioMetadata, StatusResponseDTO
)
from common.services.queue import enqueue_task

QUEUE_NAME="stt_tasks"

router = APIRouter()

@router.post("/sessions", response_model=SessionCreateResponseDTO)
async def create_session(db: AsyncSession = Depends(get_db)):
    new_operation = Operation(status="created")

    db.add(new_operation)
    await db.commit()
    await db.refresh(new_operation)

    return {"operation_id": new_operation.id}


@router.post("/operations/{operation_id}/params")
async def set_params(operation_id: UUID,
                     params: ProcessingParamsDTO,
                     db: AsyncSession = Depends(get_db)):
    await db.execute(update(Operation)
        .where(Operation.id == operation_id)
        .values(
            params=params.model_dump(),
            status=ProcessingStatus.params_received
        )
    )

    await db.commit()

    return {"status": "params_saved"}


@router.post("/operations/{operation_id}/audio")
async def upload_audio(operation_id: UUID,
                       audio_metadata: AudioMetadata,
                       db: AsyncSession = Depends(get_db)):
    operation = await db.get(Operation, operation_id)

    # отправляем задачу в worker
    enqueue_task({
        "operation_id": str(operation_id),
        "file_s3_key": audio_metadata.file_url,
        "params": operation.params if operation.params else {}
    },
        QUEUE_NAME
    )
    await db.execute(
        update(Operation)
        .where(Operation.id == operation_id)
        .values(status=ProcessingStatus.processing)
    )
    await db.commit()

    return { "status": ProcessingStatus.processing }


@router.get("/operations/{operation_id}/status", response_model=StatusResponseDTO)
async def get_status(operation_id: UUID,
                     db: AsyncSession = Depends(get_db)):
    operation = await db.get(Operation, operation_id)

    if not operation:
        return {"status": "not_found"}

    return {
        "status": operation.status,
        "result": operation.result
    }

'''async def get_operation(operation_id: UUID, db: AsyncSession) -> Operation:
    result = await db.execute(
        select(Operation)
        .where(Operation.id == operation_id)
    )

    return result.scalar_one_or_none()'''

'''async def update_model(row_id: UUID, db: AsyncSession, model: Base):
    await db.execute(
        update(model)
        .where(model.id == row_id)
        .values(status=ProcessingStatus.processing)
    )'''