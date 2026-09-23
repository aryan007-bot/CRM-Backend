from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class ApiEndpointMetric(BaseModel):
    path: str
    method: str
    request_count: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    latency_ms: float = 0.0
    p95_latency_ms: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class ApiUsageResponse(BaseModel):
    total_requests: int
    error_rate: float
    average_latency_ms: float
    p95_latency_ms: float
    endpoints: List[ApiEndpointMetric]
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ApiEndpointGroup(BaseModel):
    name: str
    endpoints: List[ApiEndpointMetric]
    state: str = "HEALTHY"
    request_count: int = 0
    error_rate: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class ApiHealthDetail(BaseModel):
    groups: List[ApiEndpointGroup]
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
