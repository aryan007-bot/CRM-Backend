import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class ServiceResponse(BaseModel):
    id: uuid.UUID
    scope: str
    organization_id: Optional[uuid.UUID] = None
    name: str
    service_type: str
    status: str
    version: str
    environment: str
    region: Optional[str] = None
    endpoint_metadata_safe: Optional[Dict[str, Any]] = None
    last_heartbeat_at: Optional[datetime] = None
    last_health_check_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceHealthLogResponse(BaseModel):
    id: uuid.UUID
    service_id: uuid.UUID
    status: str
    latency_ms: Optional[int] = None
    error_code: Optional[str] = None
    safe_message: Optional[str] = None
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)
