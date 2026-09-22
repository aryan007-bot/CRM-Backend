import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IDMixin, OrganizationMixin, TimestampMixin


class TelephonyGateway(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "telephony_gateways"
    __table_args__ = (
        Index("idx_telephony_gw_org_status", "organization_id", "status"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    gateway_type: Mapped[str] = mapped_column(String(50), default="GSM", nullable=False)  # GSM, SIP, WEBRTC
    host: Mapped[str] = mapped_column(String(255), default="localhost", nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=5060, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="ONLINE", nullable=False)  # ONLINE, OFFLINE, BUSY, ERROR
    signal_strength: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-100
    network_operator: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "Airtel", "Jio"
    active_channels: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class AiServiceStatus(Base, IDMixin):
    __tablename__ = "ai_service_status"
    __table_args__ = (
        Index("idx_ai_service_type", "service_type"),
    )

    service_type: Mapped[str] = mapped_column(String(50), nullable=False)  # STT, LLM, TTS, VAD, ASTERISK
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="HEALTHY", nullable=False)  # HEALTHY, DEGRADED, UNAVAILABLE
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
