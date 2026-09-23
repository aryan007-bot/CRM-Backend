import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, TimestampMixin


class SystemJob(Base, IDMixin, TimestampMixin):
    __tablename__ = "system_jobs"
    __table_args__ = (
        Index("idx_system_jobs_scope_status", "scope", "status"),
        Index("idx_system_jobs_queue_status", "queue_id", "status"),
        Index("idx_system_jobs_entity", "entity_type", "entity_id"),
        Index("idx_system_jobs_idempotency", "idempotency_key"),
    )

    scope: Mapped[str] = mapped_column(String(50), default="SERVICE", nullable=False)  # PLATFORM, ORGANIZATION, SERVICE
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    queue_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("queues.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    worker_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("worker_nodes.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="QUEUED", nullable=False)  # QUEUED, RUNNING, RETRYING, COMPLETED, FAILED, DEAD, CANCELLED
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[Optional[Text]] = mapped_column(Text, nullable=True)
