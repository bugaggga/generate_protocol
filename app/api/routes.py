from datetime import datetime, timezone

from uuid import UUID
import logging
import asyncio
import shutil

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.core.db import get_db
from common.core.db_service import update_status
from common.models.orm_models import Operation, RecognizeTask, OperationVersion, LlmTask

from common.models.dto import (
    ProcessingParamsDTO,
    OperationCreateResponseDTO, ProcessingStatus, AudioMetadata, StatusResponseDTO, CancelResponse,
    TaskStatus
)
from common.services.manage_files import clean_operation_catalog
from common.services.s3_client import create_presigned_post, download_protocol, delete_operation_files

SERVICE_NAME="[API]"
tmp_dir = "/app/tmp"

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
        .filter_by(id=params.operation_id)
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

    operation = await db.get(Operation, operation_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Not found")

    # 1. Деактивация всех предыдущих активных версий
    await db.execute(
        update(OperationVersion)
        .filter_by(operation_id=operation_id, is_active=True)
        .values(is_active=False, deactivated_at=datetime.now(timezone.utc))
    )

    # 2. Создание новой версии
    new_version = OperationVersion(
        operation_id=operation_id,
        is_active=True,
        params=params.form.model_dump()
    )
    db.add(new_version)
    await db.flush()
    await db.refresh(new_version)

    await db.execute(
        update(Operation)
        .filter_by(id=operation_id)
        .values(
            status=ProcessingStatus.processing,
        )
    )

    # 3. Создание задачи recognize до публикации в очередь
    recognize_task = RecognizeTask(
        operation_id=operation_id,
        version_id=new_version.id,
        file_s3_key=params.s3_key,
        status=TaskStatus.pending,
    )
    db.add(recognize_task)
    await db.commit()

    return { "status": ProcessingStatus.processing, "versionId": str(new_version.id) }

@router.get("/operations/{operation_id}/status",
            response_model=StatusResponseDTO)
async def get_status(operation_id: UUID,
                     db: AsyncSession = Depends(get_db)):
    operation = await db.get(Operation, operation_id)
    if not operation:
        return {"status": "not_found"}

    # Ленивый переход в completed: проверяем llm_tasks один раз
    if operation.status == ProcessingStatus.processing:
        active_ver = await db.scalar(
            select(OperationVersion)
            .filter_by(operation_id=operation_id, is_active=True)
        )
        if active_ver:
            new_status = await _derive_status(db, active_ver.id)
            if new_status:
                operation.status = new_status
                await db.commit()

    return {"status": operation.status}

@router.get("/operations/{operation_id}/protocol")
async def get_protocol(operation_id: UUID,
                     db: AsyncSession = Depends(get_db)):
    active_ver = await db.scalar(
        select(OperationVersion)
        .filter_by(operation_id=operation_id, is_active=True)
    )
    if not active_ver:
        raise HTTPException(status_code=409, detail="No active version")

    llm_task = await db.scalar(
        select(LlmTask)
        .filter_by(version_id=active_ver.id)
    )
    if not llm_task:
        raise HTTPException(status_code=425, detail="Not ready")

    _, md_content = await asyncio.to_thread(
        download_protocol, str(operation_id), str(active_ver.id)
    )

    operation = await db.get(Operation, operation_id)
    operation.status = ProcessingStatus.closed
    await db.commit()

    return {
        "markdown": md_content
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

    # Деактивация активной версии — сервисы увидят is_active=False на следующей проверке
    await db.execute(
        update(OperationVersion)
        .filter_by(operation_id=operation_id, is_active=True)
        .values(is_active=False, deactivated_at=datetime.now(timezone.utc))
    )
    operation.status = ProcessingStatus.cancelling
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
        db: AsyncSession = Depends(get_db)):
    await asyncio.to_thread(delete_operation_files,str(operation_id))
    clean_operation_catalog(str(operation_id))
    shutil.rmtree(f"{tmp_dir}/{str(operation_id)}", ignore_errors=True)

    try:
        await update_status(db, str(operation_id), ProcessingStatus.closed)
        await db.commit()
    except ValueError:
        pass

    return {
        "status": ProcessingStatus.closed
    }


async def _derive_status(db: AsyncSession, version_id) -> ProcessingStatus | None:
    """
    Выводит статус операции из статусов её task-записей.
    Возвращает None, если переход не требуется (всё ещё в работе).
    """
    # 1. Финальный шаг — llm_task. Его статус решает исход.
    llm_task = await db.scalar(
        select(LlmTask).filter_by(version_id=version_id)
    )
    if llm_task:
        if llm_task.status == TaskStatus.done:
            return ProcessingStatus.completed
        if llm_task.status == TaskStatus.failed:
            return ProcessingStatus.failed
        return None  # pending / queued / processing — ждём

    # 2. llm_task ещё не создан — проверяем предыдущий шаг
    rec_task = await db.scalar(
        select(RecognizeTask).filter_by(version_id=version_id)
    )
    if rec_task and rec_task.status == TaskStatus.failed:
        return ProcessingStatus.failed

    return None  # recognize ещё работает