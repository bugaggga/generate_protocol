from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from common.core.db import get_db
from common.core.db_service import update_status
from common.models.orm_models import Operation

from common.models.dto import (
    ProcessingParamsDTO,
    OperationCreateResponseDTO, ProcessingStatus, AudioMetadata, StatusResponseDTO, CancelResponse
)
from common.services.manage_files import clean_operation_catalog
from common.services.queue import enqueue_task
from common.services.s3_client import create_presigned_post, delete_object

QUEUE_NAME="recognize_tasks"
SERVICE_NAME="[API]"

router = APIRouter(prefix="/api")

@router.post("/operations", response_model=OperationCreateResponseDTO)
async def create_operation(audio_metadata: AudioMetadata,
                         db: AsyncSession = Depends(get_db)):
    new_operation = Operation(status="created")
    db.add(new_operation)
    await db.commit()
    await db.refresh(new_operation)

    s3_key = f"operations/{new_operation.id}/{audio_metadata.file_name}"
    s3_presigned_url = create_presigned_post(s3_key)

    logging.info(f"{SERVICE_NAME} Created URL: {s3_presigned_url}")

    return { "operation_id": new_operation.id,
             "s3_key": s3_key,
             "s3_presigned_url": s3_presigned_url,
    }


@router.post("/operations/params")
async def set_params(params: ProcessingParamsDTO,
                     db: AsyncSession = Depends(get_db)):
    await db.execute(update(Operation)
        .where(Operation.id == params.operation_id)
        .values(
            params=params.form,
            status=ProcessingStatus.params_received
        )
    )

    await db.commit()

    return { "status": ProcessingStatus.params_received }


@router.post("/operations/{operation_id}/process")
async def upload_audio(operation_id: UUID,
                       params: ProcessingParamsDTO,
                       db: AsyncSession = Depends(get_db)):
    logging.info(f"{SERVICE_NAME} Received form")
    '''for key, value in params.form.items():
        if key == "blocks":
            value = '\n'.join([f"title: {block['title']}" for block in value])
        logging.info(f"{key}: {value}")'''
    operation = await db.get(Operation, operation_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Not found")

    # Берём максимум из всех когда-либо использованных версий
    all_versions = list(operation.prev_versions or [])
    if operation.active_version:
        all_versions.append(operation.active_version)

    current = max(all_versions) if len(all_versions) > 0  else 0
    new_version = current + 1

    prev = all_versions  # все предыдущие, включая только что вытесненную активную

    await db.execute(
        update(Operation)
        .where(Operation.id == params.operation_id)
        .values(
            params=params.form.model_dump(),
            status=ProcessingStatus.processing,
            active_version=new_version,
            prev_versions=prev,
        )
    )
    await db.commit()

    # отправляем задачу в worker
    enqueue_task({
        "operation_id": str(operation_id),
        "file_s3_key": params.s3_key,
        "version": new_version,
    }, QUEUE_NAME)

    return { "status": ProcessingStatus.processing, "version": new_version }

@router.get("/operations/{operation_id}/status", response_model=StatusResponseDTO)
async def get_status(operation_id: UUID,
                     db: AsyncSession = Depends(get_db)):
    operation = await db.get(Operation, operation_id)

    if not operation:
        return {"status": "not_found"}

    return {
        "status": operation.status
    }

@router.get("/operations/{operation_id}/protocol")
async def get_protocol(operation_id: UUID,
                     db: AsyncSession = Depends(get_db)):
    operation = await db.get(Operation, operation_id)

    if not operation:
        return {"status": "not_found"}

    await update_status(db, operation.id, ProcessingStatus.closed)

    return {
        "markdown": operation.md_res
    }

@router.post("/operations/{operation_id}/cancel", response_model=CancelResponse)
async def cancel_operation(
        operation_id: UUID,
        db: AsyncSession = Depends(get_db)):
    operation = await db.get(Operation, operation_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")

    # Нельзя отменить уже завершённые операции
    terminal_statuses = {
        ProcessingStatus.completed, ProcessingStatus.failed,
        ProcessingStatus.cancelled, ProcessingStatus.closed}
    if operation.status in terminal_statuses:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel operation with status '{operation.status}'"
        )

    # Убираем активную версию → воркер увидит несоответствие
    prev = list(operation.prev_versions or [])
    if operation.active_version:
        prev.append(operation.active_version)

    await db.execute(
        update(Operation)
        .where(Operation.id == operation_id)
        .values(
            status=ProcessingStatus.cancelling,
            active_version=None,  # ← версии больше нет
            prev_versions=prev,
        )
    )
    await db.commit()

    return CancelResponse(
        operation_id=operation_id,
        status=ProcessingStatus.cancelling,
        message="Cancellation accepted. Processing will stop shortly."
    )

@router.post("/get/presigned_url")
async def get_presigned_url(s3_key: str = Body(embed=True)):
    presigned_data = create_presigned_post(s3_key)

    return {
        "presigned_data": presigned_data
    }

@router.delete("/operations/{operation_id}")
async def delete_operation(
        operation_id: UUID,
        s3_key: str = Body(embed=True),
        db: AsyncSession = Depends(get_db)):
    delete_object(s3_key)
    clean_operation_catalog(str(operation_id))

    await update_status(db, str(operation_id), ProcessingStatus.closed)
    await db.commit()

    return {
        "status": ProcessingStatus.closed
    }