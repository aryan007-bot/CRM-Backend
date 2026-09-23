import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class TelephonyInfrastructureResponse(BaseModel):
    id: uuid.UUID
    scope: str
    organization_id: Optional[uuid.UUID] = None
    type: str
    name: str
    status: str
    registration_status: str
    capacity: int
    active_channels: int
    failed_calls: int
    last_heartbeat_at: Optional[datetime] = None
    metadata_safe: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
