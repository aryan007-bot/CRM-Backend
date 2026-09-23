import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class IncidentEventResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    event_type: str
    message: str
    source: str
    timestamp: datetime
    metadata_safe: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class IncidentResponse(BaseModel):
    id: uuid.UUID
    scope: str
    organization_id: Optional[uuid.UUID] = None
    title: str
    description: str
    severity: str
    status: str
    source: str
    affected_service_id: Optional[uuid.UUID] = None
    correlation_key: Optional[str] = None
    started_at: datetime
    resolved_at: Optional[datetime] = None
    assigned_to: Optional[uuid.UUID] = None
    events: Optional[List[IncidentEventResponse]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertCreate(BaseModel):
    name: str
    metric: str
    operator: str  # GT, GTE, LT, LTE, EQ
    threshold: int
    window_seconds: int = 300
    severity: str = "MEDIUM"
    enabled: bool = True
    scope: str = "PLATFORM"
    organization_id: Optional[uuid.UUID] = None


class AlertUpdate(BaseModel):
    name: Optional[str] = None
    metric: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[int] = None
    window_seconds: Optional[int] = None
    severity: Optional[str] = None
    enabled: Optional[bool] = None


class AlertResponse(BaseModel):
    id: uuid.UUID
    scope: str
    organization_id: Optional[uuid.UUID] = None
    name: str
    metric: str
    operator: str
    threshold: int
    window_seconds: int
    severity: str
    enabled: bool
    state: str
    correlation_key: Optional[str] = None
    last_triggered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertActionRequest(BaseModel):
    action: str

