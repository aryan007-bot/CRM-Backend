from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class TelephonyGatewayCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    gateway_type: str = Field(default="GSM", max_length=50)  # GSM, SIP, WEBRTC
    host: str = Field(default="localhost", max_length=255)
    port: int = Field(default=5060, ge=1, le=65535)


class TelephonyGatewayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    gateway_type: str
    host: str
    port: int
    status: str
    signal_strength: Optional[int] = None
    network_operator: Optional[str] = None
    active_channels: int
    last_seen_at: datetime
    created_at: datetime


class GatewayHeartbeat(BaseModel):
    signal_strength: Optional[int] = Field(None, ge=0, le=100)
    network_operator: Optional[str] = None
    active_channels: int = Field(0, ge=0)


class TelephonyStatusOut(BaseModel):
    asterisk_status: str
    active_channels: int
    gateways_online: int
    gateways_total: int


class AiServiceStatusOut(BaseModel):
    service_type: str
    provider: str
    model: Optional[str] = None
    status: str
    latency_ms: Optional[int] = None
    last_checked_at: datetime


class AiStatusSummaryOut(BaseModel):
    services: List[AiServiceStatusOut]
    overall_status: str
