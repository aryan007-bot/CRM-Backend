import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON as FallbackJSON

from app.db.base import GUID, Base, IDMixin, TimestampMixin


class AiService(Base, IDMixin, TimestampMixin):
    __tablename__ = "ai_services"
    __table_args__ = (
        Index("idx_ai_services_scope_status", "scope", "status"),
        Index("idx_ai_services_type", "service_type"),
    )

    scope: Mapped[str] = mapped_column(String(50), default="SERVICE", nullable=False)  # PLATFORM, ORGANIZATION, SERVICE
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    service_type: Mapped[str] = mapped_column(String(50), nullable=False)  # AI_GATEWAY, LLM, STT, TTS, VAD, ANALYSIS, VOICE
    status: Mapped[str] = mapped_column(String(50), default="HEALTHY", nullable=False)  # HEALTHY, DEGRADED, UNAVAILABLE, UNKNOWN
    version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    active_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    queue_depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    p95_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_rate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_health_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AiProvider(Base, IDMixin, TimestampMixin):
    __tablename__ = "ai_providers"
    __table_args__ = (
        Index("idx_ai_providers_scope_status", "scope", "status"),
        Index("idx_ai_providers_type", "provider_type"),
    )

    scope: Mapped[str] = mapped_column(String(50), default="PLATFORM", nullable=False)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)  # LLM, STT, TTS, VAD, EMBEDDING
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="HEALTHY", nullable=False)  # HEALTHY, DEGRADED, RATE_LIMITED, QUOTA_EXCEEDED, UNAVAILABLE, INVALID, UNKNOWN
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    credential_status: Mapped[str] = mapped_column(String(50), default="NOT_CONFIGURED", nullable=False)  # CONFIGURED, NOT_CONFIGURED, INVALID, EXPIRED
    credential_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    health_status: Mapped[str] = mapped_column(String(50), default="HEALTHY", nullable=False)
    last_health_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    models: Mapped[List["AiModel"]] = relationship(
        "AiModel",
        back_populates="provider",
        cascade="all, delete-orphan",
    )
    quotas: Mapped[List["ProviderQuota"]] = relationship(
        "ProviderQuota",
        back_populates="provider",
        cascade="all, delete-orphan",
    )


class AiModel(Base, IDMixin, TimestampMixin):
    __tablename__ = "ai_models"
    __table_args__ = (
        Index("idx_ai_models_provider", "provider_id"),
        Index("idx_ai_models_type", "model_type"),
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("ai_providers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False)  # LLM, STT, TTS, VAD
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="HEALTHY", nullable=False)
    streaming_supported: Mapped[Optional[bool]] = mapped_column(Boolean, default=True, nullable=True)
    tool_support: Mapped[Optional[bool]] = mapped_column(Boolean, default=True, nullable=True)
    context_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata_safe: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=True,
        default=dict,
    )

    provider: Mapped["AiProvider"] = relationship("AiProvider", back_populates="models")


class AiRoutingRule(Base, IDMixin, TimestampMixin):
    __tablename__ = "ai_routing_rules"
    __table_args__ = (
        Index("idx_ai_routing_scope_service", "scope", "service_type"),
    )

    scope: Mapped[str] = mapped_column(String(50), default="PLATFORM", nullable=False)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    service_type: Mapped[str] = mapped_column(String(50), nullable=False)
    primary_provider_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("ai_providers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    primary_model_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("ai_models.id", ondelete="SET NULL"),
        nullable=True,
    )
    fallbacks: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=True,
        default=list,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    conditions: Mapped[Optional[List[str]]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=True,
        default=list,
    )


class AiRequestMetric(Base, IDMixin):
    __tablename__ = "ai_request_metrics"
    __table_args__ = (
        Index("idx_ai_req_metrics_provider_time", "provider_id", "timestamp"),
        Index("idx_ai_req_metrics_scope_time", "scope", "timestamp"),
    )

    scope: Mapped[str] = mapped_column(String(50), default="PLATFORM", nullable=False)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    service_type: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("ai_providers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    model_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("ai_models.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    request_type: Mapped[str] = mapped_column(String(50), default="chat", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="SUCCESS", nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    queue_wait_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    processing_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    audio_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProviderQuota(Base, IDMixin):
    __tablename__ = "provider_quotas"
    __table_args__ = (
        Index("idx_provider_quotas_provider_metric", "provider_id", "metric"),
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("ai_providers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(String(50), default="PLATFORM", nullable=False)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    metric: Mapped[str] = mapped_column(String(50), default="REQUESTS", nullable=False)  # REQUESTS, TOKENS, AUDIO_SECONDS, MINUTES, CUSTOM
    configured_limit: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    current_usage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    remaining: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="CONFIGURED", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    provider: Mapped["AiProvider"] = relationship("AiProvider", back_populates="quotas")
