import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON as FallbackJSON

from app.db.base import GUID, Base, IDMixin, TimestampMixin


class Incident(Base, IDMixin, TimestampMixin):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("idx_incidents_scope_status", "scope", "status"),
        Index("idx_incidents_severity", "severity"),
        Index("idx_incidents_correlation", "correlation_key"),
    )

    scope: Mapped[str] = mapped_column(String(50), default="PLATFORM", nullable=False)  # PLATFORM, ORGANIZATION, SERVICE
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default="MEDIUM", nullable=False)  # INFO, LOW, MEDIUM, HIGH, CRITICAL
    status: Mapped[str] = mapped_column(String(50), default="OPEN", nullable=False)  # OPEN, INVESTIGATING, MITIGATED, RESOLVED, CLOSED
    source: Mapped[str] = mapped_column(String(100), default="SYSTEM", nullable=False)
    affected_service_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("services.id", ondelete="SET NULL"),
        nullable=True,
    )
    correlation_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    events: Mapped[List["IncidentEvent"]] = relationship(
        "IncidentEvent",
        back_populates="incident",
        cascade="all, delete-orphan",
    )


class IncidentEvent(Base, IDMixin):
    __tablename__ = "incident_events"
    __table_args__ = (
        Index("idx_incident_events_incident_time", "incident_id", "timestamp"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # DETECTED, ACKNOWLEDGED, SERVICE_DEGRADED, WORKER_RECOVERED, QUEUE_NORMALIZED, RESOLVED
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), default="SYSTEM", nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata_safe: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=True,
        default=dict,
    )

    incident: Mapped["Incident"] = relationship("Incident", back_populates="events")


class AlertDefinition(Base, IDMixin, TimestampMixin):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("idx_alerts_scope_state", "scope", "state"),
        Index("idx_alerts_correlation", "correlation_key"),
    )

    scope: Mapped[str] = mapped_column(String(50), default="PLATFORM", nullable=False)  # PLATFORM, ORGANIZATION, SERVICE
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str] = mapped_column(String(20), nullable=False)  # GT, GTE, LT, LTE, EQ
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default="MEDIUM", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    state: Mapped[str] = mapped_column(String(50), default="RESOLVED", nullable=False)  # ACTIVE, ACKNOWLEDGED, RESOLVED, DISABLED
    correlation_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
