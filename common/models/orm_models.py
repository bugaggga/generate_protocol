from sqlalchemy.orm import declarative_base, mapped_column, Mapped
from sqlalchemy import (
    DateTime, Enum, UUID, JSON, String, Integer, ARRAY
)

from datetime import datetime, timezone
import uuid

from common.models.dto import ProcessingStatus

Base = declarative_base()


class Operation(Base):

    __tablename__ = "operations"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4, index=False)

    status : Mapped[ProcessingStatus]= mapped_column(Enum(ProcessingStatus, name="process_status"), nullable=False)

    params: Mapped[dict] = mapped_column(JSON, nullable=True)

    json_res: Mapped[dict] = mapped_column(JSON, nullable=True)

    md_res: Mapped[str] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc))

    '''cancelled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True)'''

    # ── Версионирование ──────────────────────────────────────────────────────
    active_version = mapped_column(Integer, nullable=True)  # версия текущего запуска
    prev_versions = mapped_column(ARRAY(Integer), default=list)  # история отменённых версий