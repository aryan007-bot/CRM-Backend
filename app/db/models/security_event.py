import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON as FallbackJSON

from app.db.base import GUID, Base, IDMixin


class SecurityEvent(Base, IDMixin):
    __tablename__ = "security_events"
    __table_args__ = (
        Index("idx_security_events_scope_time", "scope", "timestamp"),
        Index("idx_security_events_type", "event_type"),
        Index("idx_security_events_severity", "severity"),
    )

    scope: Mapped[str] = mapped_column(String(50), default="PLATFORM", nullable=False)  # PLATFORM, ORGANIZATION, SERVICE
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default="MEDIUM", nullable=False)  # INFO, LOW, MEDIUM, HIGH, CRITICAL
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    safe_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=True,
        default=dict,
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OperationalEvent(Base, IDMixin):
    __tablename__ = "operational_events"
    __table_args__ = (
        Index("idx_op_events_scope_time", "scope", "timestamp"),
        Index("idx_op_events_type", "event_type"),
        Index("idx_op_events_entity", "entity_type", "entity_id"),
    )

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[str] = mapped_column(String(50), default="PLATFORM", nullable=False)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    severity: Mapped[str] = mapped_column(String(50), default="INFO", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_safe: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=True,
        default=dict,
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
