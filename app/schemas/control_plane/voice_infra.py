from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict
from app.schemas.control_plane.system import LatencyStats
from app.schemas.control_plane.worker import WorkerResponse


class VoiceServiceHealthResponse(BaseModel):
    id: str
    name: str
    state: str = "HEALTHY"
    latency: Optional[LatencyStats] = None
    usage_count: Optional[int] = 0
    failures: Optional[int] = 0
    worker_count: Optional[int] = 1
    scope: str = "PLATFORM"
    organization_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)


class VoiceInfraResponse(BaseModel):
    tts_services: List[VoiceServiceHealthResponse]
    workers: List[WorkerResponse]
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
