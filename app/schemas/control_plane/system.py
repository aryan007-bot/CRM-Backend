from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class ComponentHealth(BaseModel):
    name: str
    status: str  # HEALTHY, DEGRADED, UNAVAILABLE, UNKNOWN
    latency_ms: Optional[int] = None
    last_checked_at: Optional[datetime] = None
    message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SystemHealthResponse(BaseModel):
    overall_status: str  # OPERATIONAL, DEGRADED, UNAVAILABLE, UNKNOWN
    components: List[ComponentHealth]
    active_incident_count: int = 0
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReadinessCheckItem(BaseModel):
    name: str
    status: str  # PASS, WARN, FAIL
    message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ReadinessResponse(BaseModel):
    ready: bool
    checks: List[ReadinessCheckItem]
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LatencyStats(BaseModel):
    avg_ms: Optional[float] = None
    p50_ms: Optional[float] = None
    p95_ms: Optional[float] = None
    p99_ms: Optional[float] = None


class DatabaseStorageStats(BaseModel):
    used_bytes: Optional[int] = None
    total_bytes: Optional[int] = None


class DatabaseHealthResponse(BaseModel):
    connected: bool
    state: str = "HEALTHY"
    latency: Optional[LatencyStats] = None
    pool_utilization: Optional[float] = None
    active_connections: Optional[int] = None
    slow_queries: Optional[int] = 0
    version: Optional[str] = None
    migration_status: Optional[str] = None
    storage: Optional[DatabaseStorageStats] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

