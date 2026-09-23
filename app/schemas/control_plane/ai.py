import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class AiServiceResponse(BaseModel):
    id: uuid.UUID
    scope: str
    organization_id: Optional[uuid.UUID] = None
    service_type: str
    status: str
    version: str
    active_jobs: int
    queue_depth: int
    average_latency_ms: int
    p95_latency_ms: int
    error_rate: int
    last_health_check: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AiProviderCreate(BaseModel):
    name: str
    provider_type: str  # LLM, STT, TTS, VAD, EMBEDDING
    scope: str = "PLATFORM"
    organization_id: Optional[uuid.UUID] = None
    priority: int = 1
    api_key: Optional[str] = None  # Securely ingested, never returned


class AiProviderUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    api_key: Optional[str] = None


class AiProviderResponse(BaseModel):
    id: uuid.UUID
    scope: str
    organization_id: Optional[uuid.UUID] = None
    name: str
    provider_type: str
    enabled: bool
    status: str
    priority: int
    credential_status: str  # CONFIGURED, NOT_CONFIGURED, INVALID, EXPIRED
    health_status: str
    last_health_check: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AiModelCreate(BaseModel):
    provider_id: uuid.UUID
    name: str
    model_type: str
    streaming_supported: Optional[bool] = True
    tool_support: Optional[bool] = True
    context_limit: Optional[int] = None
    metadata_safe: Optional[Dict[str, Any]] = None


class AiModelUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    status: Optional[str] = None
    streaming_supported: Optional[bool] = None
    tool_support: Optional[bool] = None
    context_limit: Optional[int] = None
    metadata_safe: Optional[Dict[str, Any]] = None


class AiModelResponse(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    name: str
    model_type: str
    enabled: bool
    status: str
    streaming_supported: Optional[bool] = True
    tool_support: Optional[bool] = True
    context_limit: Optional[int] = None
    metadata_safe: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AiRoutingRuleCreate(BaseModel):
    service_type: str
    primary_provider_id: uuid.UUID
    primary_model_id: Optional[uuid.UUID] = None
    fallbacks: Optional[List[Dict[str, Any]]] = None
    enabled: bool = True
    priority: int = 1
    conditions: Optional[List[str]] = None
    scope: str = "PLATFORM"
    organization_id: Optional[uuid.UUID] = None


class AiRoutingRuleUpdate(BaseModel):
    primary_provider_id: Optional[uuid.UUID] = None
    primary_model_id: Optional[uuid.UUID] = None
    fallbacks: Optional[List[Dict[str, Any]]] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    conditions: Optional[List[str]] = None


class AiRoutingRuleResponse(BaseModel):
    id: uuid.UUID
    scope: str
    organization_id: Optional[uuid.UUID] = None
    service_type: str
    primary_provider_id: uuid.UUID
    primary_model_id: Optional[uuid.UUID] = None
    fallbacks: Optional[List[Dict[str, Any]]] = None
    enabled: bool
    priority: int
    conditions: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AiUsageSummaryResponse(BaseModel):
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    fallback_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_audio_duration_seconds: float = 0.0


class AiLatencySummaryResponse(BaseModel):
    service_type: str
    provider: Optional[str] = None
    average_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0


class ProviderQuotaResponse(BaseModel):
    provider_id: uuid.UUID
    provider_name: str
    metric: str
    configured_limit: int
    current_usage: int
    remaining: int
    reset_at: Optional[datetime] = None
    source: str

    model_config = ConfigDict(from_attributes=True)
