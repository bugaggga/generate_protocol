from sqlalchemy.orm import declarative_base, mapped_column, Mapped, relationship
from sqlalchemy import (
    DateTime, Enum, UUID, JSON, String, ForeignKey, Boolean, text, Index
)

from datetime import datetime, timezone
import uuid

from common.models.dto import ProcessingStatus, TaskStatus

Base = declarative_base()


class Operation(Base):

    __tablename__ = "operations"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4, index=False)

    status : Mapped[ProcessingStatus]= mapped_column(Enum(ProcessingStatus,
                                                          name="process_status"),
                                                     nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc))

    recognize_tasks = relationship("RecognizeTask", back_populates="operation", passive_deletes=True)
    llm_tasks = relationship("LlmTask", back_populates="operation", passive_deletes=True)
    operation_versions = relationship("OperationVersion", back_populates="operation", passive_deletes=True)


class BaseTask(Base):
    __abstract__ = True

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4, index=False)

    operation_id = mapped_column(UUID,
                                 ForeignKey("operations.id",
                                            ondelete="CASCADE"),
                                 nullable=False)

    version_id = mapped_column(UUID,
                                 ForeignKey("operation_versions.id",
                                            ondelete="CASCADE"),
                                 nullable=False)

    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, name='task_status'),
                                               nullable=False)

    params: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc))

class RecognizeTask(BaseTask):
    __tablename__ = "recognize_tasks"

    file_s3_key: Mapped[str] = mapped_column(String, nullable=False)

    operation = relationship("Operation", back_populates="recognize_tasks")


class LlmTask(BaseTask):
    __tablename__ = "llm_tasks"

    transcript_s3_key: Mapped[str] = mapped_column(String, nullable=False)
    frames_key: Mapped[str] = mapped_column(String, nullable=True)

    operation = relationship("Operation", back_populates="llm_tasks")

class OperationVersion(Base):
    __tablename__ = "operation_versions"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4, index=False)
    operation_id = mapped_column(UUID, ForeignKey("operations.id"), nullable=False, index=True)
    is_active = mapped_column(Boolean, nullable=False, default=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False,
                               default=lambda: datetime.now(timezone.utc))
    deactivated_at = mapped_column(DateTime(timezone=True), nullable=True)

    operation = relationship("Operation", back_populates="operation_versions")

    __table_args__ = (
        Index(
            "uq_one_active_version_per_op",
            "operation_id",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )