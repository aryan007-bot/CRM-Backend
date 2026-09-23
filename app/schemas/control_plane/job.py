import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    id: uuid.UUID
    scope: str
    organization_id: Optional[uuid.UUID] = None
    queue_id: Optional[uuid.UUID] = None
    worker_id: Optional[uuid.UUID] = None
    job_type: str
    status: str
    attempts: int
    max_attempts: int
    idempotency_key: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[uuid.UUID] = None
    scheduled_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobRetryResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    attempts: int
    message: str


class JobActionRequest(BaseModel):
    action: str

