import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, TimestampMixin


class WorkerNode(Base, IDMixin, TimestampMixin):
    __tablename__ = "worker_nodes"
    __table_args__ = (
        Index("idx_worker_nodes_scope_status", "scope", "status"),
        Index("idx_worker_nodes_type", "worker_type"),
        Index("idx_worker_nodes_heartbeat", "last_heartbeat_at"),
    )

    scope: Mapped[str] = mapped_column(String(50), default="SERVICE", nullable=False)  # PLATFORM, ORGANIZATION, SERVICE
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    worker_type: Mapped[str] = mapped_column(String(50), nullable=False)  # CAMPAIGN, DIAL_QUEUE, RETRY, ANALYSIS, FOLLOW_UP, EXPORT, STT, TTS, LLM, VOICE, MONITORING, OTHER
    status: Mapped[str] = mapped_column(String(50), default="STARTING", nullable=False)  # STARTING, HEALTHY, DEGRADED, DRAINING, STOPPED, FAILED, UNKNOWN
    version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    environment: Mapped[str] = mapped_column(String(50), default="production", nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    concurrency: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    active_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    commands: Mapped[List["WorkerCommand"]] = relationship(
        "WorkerCommand",
        back_populates="worker",
        cascade="all, delete-orphan",
    )


class WorkerCommand(Base, IDMixin):
    __tablename__ = "worker_commands"
    __table_args__ = (
        Index("idx_worker_cmd_worker_status", "worker_id", "status"),
        Index("idx_worker_cmd_idempotency", "idempotency_key"),
    )

    worker_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("worker_nodes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    command: Mapped[str] = mapped_column(String(50), nullable=False)  # DRAIN, RESUME, RESTART, DISABLE
    requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(50), default="REQUESTED", nullable=False)  # REQUESTED, ACKNOWLEDGED, RUNNING, COMPLETED, FAILED, CANCELLED
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    worker: Mapped["WorkerNode"] = relationship("WorkerNode", back_populates="commands")
