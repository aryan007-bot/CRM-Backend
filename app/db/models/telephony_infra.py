import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON as FallbackJSON

from app.db.base import GUID, Base, IDMixin, TimestampMixin


class TelephonyInfrastructure(Base, IDMixin, TimestampMixin):
    __tablename__ = "telephony_infrastructure"
    __table_args__ = (
        Index("idx_telephony_infra_scope_status", "scope", "status"),
        Index("idx_telephony_infra_type", "type"),
    )

    scope: Mapped[str] = mapped_column(String(50), default="SERVICE", nullable=False)  # PLATFORM, ORGANIZATION, SERVICE
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # ASTERISK, SIP_TRUNK, SIP_GATEWAY, GSM_GATEWAY, OTHER
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="ONLINE", nullable=False)  # ONLINE, OFFLINE, DEGRADED, UNKNOWN
    registration_status: Mapped[str] = mapped_column(String(50), default="REGISTERED", nullable=False)  # REGISTERED, UNREGISTERED, FAILED
    capacity: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    active_channels: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_safe: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=True,
        default=dict,
    )
