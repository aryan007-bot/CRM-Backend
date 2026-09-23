from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class LogEntryResponse(BaseModel):
    id: str
    timestamp: datetime
    level: str
    service: str
    message: str
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)
