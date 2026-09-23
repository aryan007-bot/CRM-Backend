import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class SecurityEventResponse(BaseModel):
    id: uuid.UUID
    scope: str
    organization_id: Optional[uuid.UUID] = None
    event_type: str
    severity: str
    actor_id: Optional[uuid.UUID] = None
    ip_address: Optional[str] = None
    resource_type: str
    resource_id: Optional[str] = None
    safe_details: Optional[Dict[str, Any]] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class OperationalEventResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    scope: str
    organization_id: Optional[uuid.UUID] = None
    entity_type: str
    entity_id: Optional[str] = None
    severity: str
    message: str
    payload_safe: Optional[Dict[str, Any]] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
