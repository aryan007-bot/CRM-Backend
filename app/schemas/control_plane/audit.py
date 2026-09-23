import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    action: str
    actor_id: Optional[uuid.UUID] = None
    actor_email: Optional[str] = None
    actor_name: Optional[str] = None
    target_id: Optional[str] = None
    target_type: Optional[str] = None
    occurred_at: datetime
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)
