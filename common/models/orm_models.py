from sqlalchemy.orm import declarative_base, mapped_column, Mapped
from sqlalchemy import (
    DateTime, Enum, UUID, JSON
)

from datetime import datetime, timezone

from common.models.dto import ProcessingStatus

Base = declarative_base()


class Operation(Base):

    __tablename__ = "operations"

    id = mapped_column(UUID, primary_key=True, index=False)

    status : Mapped[ProcessingStatus]= mapped_column(Enum(ProcessingStatus, name="process_status"), nullable=False)

    params: Mapped[dict] = mapped_column(JSON, nullable=True)

    result: Mapped[dict] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc))