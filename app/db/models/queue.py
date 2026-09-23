import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, TimestampMixin


class QueueRegistryItem(Base, IDMixin, TimestampMixin):
    __tablename__ = "queues"
    __table_args__ = (
        Index("idx_queues_scope_status", "scope", "status"),
        Index("idx_queues_type", "queue_type"),
    )

    scope: Mapped[str] = mapped_column(String(50), default="SERVICE", nullable=False)  # PLATFORM, ORGANIZATION, SERVICE
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    queue_type: Mapped[str] = mapped_column(String(50), nullable=False)  # DIAL, ANALYSIS, FOLLOW_UP, EXPORT, STT, TTS, VOICE, OTHER
    status: Mapped[str] = mapped_column(String(50), default="HEALTHY", nullable=False)  # HEALTHY, DEGRADED, PAUSED, FAILED, UNKNOWN
    backend_reference_safe: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    metrics: Mapped[List["QueueMetricSnapshot"]] = relationship(
        "QueueMetricSnapshot",
        back_populates="queue",
        cascade="all, delete-orphan",
    )


class QueueMetricSnapshot(Base, IDMixin):
    __tablename__ = "queue_metrics"
    __table_args__ = (
        Index("idx_queue_metrics_queue_captured", "queue_id", "captured_at"),
    )

    queue_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("queues.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    pending: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    running: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retrying: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dead: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    throughput: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    oldest_job_age_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    worker_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    queue: Mapped["QueueRegistryItem"] = relationship("QueueRegistryItem", back_populates="metrics")
