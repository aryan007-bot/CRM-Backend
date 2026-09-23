import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class WorkerHeartbeatRequest(BaseModel):
    worker_id: uuid.UUID
    status: str = "HEALTHY"
    active_jobs: int = 0
    concurrency: Optional[int] = None
    version: Optional[str] = None


class WorkerActionRequest(BaseModel):
    action: Optional[str] = None
    idempotency_key: Optional[str] = None



class WorkerCommandResponse(BaseModel):
    id: uuid.UUID
    worker_id: uuid.UUID
    command: str
    requested_by: Optional[uuid.UUID] = None
    status: str
    requested_at: datetime
    acknowledged_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    idempotency_key: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class WorkerResponse(BaseModel):
    id: uuid.UUID
    scope: str
    organization_id: Optional[uuid.UUID] = None
    worker_type: str
    status: str
    version: str
    environment: str
    hostname: str
    concurrency: int
    active_jobs: int
    last_heartbeat_at: Optional[datetime] = None
    started_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
