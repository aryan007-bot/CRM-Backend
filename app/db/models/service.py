import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON as FallbackJSON

from app.db.base import GUID, Base, IDMixin, TimestampMixin


class PlatformService(Base, IDMixin, TimestampMixin):
    __tablename__ = "services"
    __table_args__ = (
        Index("idx_services_scope_status", "scope", "status"),
        Index("idx_services_type_env", "service_type", "environment"),
    )

    scope: Mapped[str] = mapped_column(String(50), default="PLATFORM", nullable=False)  # PLATFORM, ORGANIZATION, SERVICE
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    service_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="UNKNOWN", nullable=False)  # HEALTHY, DEGRADED, UNAVAILABLE, UNKNOWN
    version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    environment: Mapped[str] = mapped_column(String(50), default="production", nullable=False)
    region: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    endpoint_metadata_safe: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=True,
        default=dict,
    )
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_health_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    health_logs: Mapped[List["ServiceHealthLog"]] = relationship(
        "ServiceHealthLog",
        back_populates="service",
        cascade="all, delete-orphan",
    )


class ServiceHealthLog(Base, IDMixin):
    __tablename__ = "service_health_logs"
    __table_args__ = (
        Index("idx_service_health_logs_service_checked", "service_id", "checked_at"),
    )

    service_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("services.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    safe_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    service: Mapped["PlatformService"] = relationship("PlatformService", back_populates="health_logs")
