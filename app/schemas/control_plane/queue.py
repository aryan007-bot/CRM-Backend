import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class QueueMetricSnapshotResponse(BaseModel):
    id: uuid.UUID
    queue_id: uuid.UUID
    pending: int
    running: int
    retrying: int
    failed: int
    dead: int
    throughput: int
    oldest_job_age_seconds: int
    worker_count: int
    latency_ms: int
    captured_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QueueResponse(BaseModel):
    id: uuid.UUID
    scope: str
    organization_id: Optional[uuid.UUID] = None
    name: str
    queue_type: str
    status: str
    backend_reference_safe: Optional[str] = None
    current_metrics: Optional[QueueMetricSnapshotResponse] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QueueActionRequest(BaseModel):
    action: str

