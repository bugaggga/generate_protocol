from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from uuid import UUID


class ProcessingStatus(str, Enum):
    created = "created"
    params_received = "params_received"
    audio_uploaded = "audio_uploaded"
    processing = "processing"
    partially_completed = "partially_completed"
    completed = "completed"
    failed = "failed"


class ProcessingParamsDTO(BaseModel):
    template_id: str
    #language: str = "ru"
    #diarization: bool = True
    #metadata: Optional[Dict[str, Any]] = None

class AudioMetadata(BaseModel):
    file_url : str

class SessionCreateResponseDTO(BaseModel):
    session_id: UUID


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
    result: Optional[ProcessingResultDTO]