from __future__ import annotations

from typing import List
from enum import Enum
from uuid import UUID
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator


# Enums
class ProcessingStatus(str, Enum):
    created = "created"
    params_received = "params_received"
    audio_uploaded = "audio_uploaded"
    processing = "processing"
    partially_completed = "partially_completed"
    completed = "completed"
    closed = "closed"
    failed = "failed"
    cancelling = "cancelling"
    cancelled = "cancelled"


# API models

class OperationCreateResponseDTO(BaseModel):
    operation_id: UUID
    s3_key: str
    s3_presigned_url: dict

class ProcessingParamsDTO(BaseModel):
    operation_id: UUID
    form: ProtocolForm
    s3_key: str

class AudioMetadata(BaseModel):
    file_name : str

class TranscriptSegmentDTO(BaseModel):
    start: float
    end: float
    speaker: str
    text: str


class ProtocolDTO(BaseModel):
    title: str
    summary: str
    decisions: List[str]
    tasks: List[str]


class ProcessingResultDTO(BaseModel):
    transcript: List[TranscriptSegmentDTO]
    protocol: ProtocolDTO


class StatusResponseDTO(BaseModel):
    status: ProcessingStatus

class CancelResponse(BaseModel):
    operation_id: UUID
    status: str
    message: str


# ---------------------------------------------------------------------------
# Block sub-models
# ---------------------------------------------------------------------------

class ColumnSchema(BaseModel):
    """Одна колонка таблицы: { key: "task" }"""
    key: str


class FieldSchema(BaseModel):
    """Одно поле объекта: { key: "Дата" }"""
    key: str


# ---------------------------------------------------------------------------
# Block variants  (discriminated union по полю `type`)
# ---------------------------------------------------------------------------

class _BlockBase(BaseModel):
    """Общие обязательные поля для всех типов блоков."""
    id: str
    order: int
    title: str
    required: bool = False
    llm_instruction: str


class TextBlock(_BlockBase):
    type: Literal["text"]


class ListBlock(_BlockBase):
    type: Literal["list"]


class FieldsBlock(_BlockBase):
    type: Literal["fields"]
    fields: list[FieldSchema] = Field(min_length=1)


class TableBlock(_BlockBase):
    type: Literal["table"]
    columns: list[ColumnSchema] = Field(min_length=1)


# Аннотированный union — Pydantic выбирает нужный класс по значению `type`
ProtocolBlock = Annotated[
    Union[TextBlock, ListBlock, FieldsBlock, TableBlock],
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Protocol form
# ---------------------------------------------------------------------------

class ProtocolForm(BaseModel):
    """Форма протокола, приходящая с фронтенда."""
    blocks: list[ProtocolBlock] = Field(min_length=1)

    @model_validator(mode="after")
    def orders_are_unique(self) -> ProtocolForm:
        orders = [b.order for b in self.blocks]
        if len(orders) != len(set(orders)):
            raise ValueError("Block `order` values must be unique")
        return self
