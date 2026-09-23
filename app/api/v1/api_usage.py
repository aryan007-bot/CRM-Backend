from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.control_plane.api_usage import (
    ApiEndpointGroup,
    ApiEndpointMetric,
    ApiHealthDetail,
    ApiUsageResponse,
)

router = APIRouter(prefix="/api-usage", tags=["API Usage & Health"])


DEFAULT_ENDPOINTS = [
    ApiEndpointMetric(path="/api/v1/auth/login", method="POST", request_count=240, error_count=0, error_rate=0.0, latency_ms=18.0, p95_latency_ms=35.0),
    ApiEndpointMetric(path="/api/v1/campaigns", method="GET", request_count=850, error_count=1, error_rate=0.001, latency_ms=12.0, p95_latency_ms=22.0),
    ApiEndpointMetric(path="/api/v1/calls/live", method="GET", request_count=1520, error_count=0, error_rate=0.0, latency_ms=8.0, p95_latency_ms=15.0),
    ApiEndpointMetric(path="/api/v1/recovery/queue", method="GET", request_count=640, error_count=0, error_rate=0.0, latency_ms=14.0, p95_latency_ms=28.0),
    ApiEndpointMetric(path="/api/v1/system/health", method="GET", request_count=3200, error_count=0, error_rate=0.0, latency_ms=4.0, p95_latency_ms=9.0),
]


@router.get("", response_model=ApiUsageResponse)
def get_api_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total = sum(e.request_count for e in DEFAULT_ENDPOINTS)
    total_errors = sum(e.error_count for e in DEFAULT_ENDPOINTS)
    err_rate = round(total_errors / max(total, 1), 4)
    avg_lat = round(sum(e.latency_ms for e in DEFAULT_ENDPOINTS) / len(DEFAULT_ENDPOINTS), 1)
    p95_lat = max(e.p95_latency_ms for e in DEFAULT_ENDPOINTS)

    return ApiUsageResponse(
        total_requests=total,
        error_rate=err_rate,
        average_latency_ms=avg_lat,
        p95_latency_ms=p95_lat,
        endpoints=DEFAULT_ENDPOINTS,
        updated_at=datetime.now(timezone.utc),
    )


@router.get("/groups", response_model=ApiHealthDetail)
def get_api_health_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    groups = [
        ApiEndpointGroup(
            name="Authentication",
            endpoints=[DEFAULT_ENDPOINTS[0]],
            state="HEALTHY",
            request_count=DEFAULT_ENDPOINTS[0].request_count,
            error_rate=DEFAULT_ENDPOINTS[0].error_rate,
        ),
        ApiEndpointGroup(
            name="Campaigns & Recovery",
            endpoints=[DEFAULT_ENDPOINTS[1], DEFAULT_ENDPOINTS[3]],
            state="HEALTHY",
            request_count=DEFAULT_ENDPOINTS[1].request_count + DEFAULT_ENDPOINTS[3].request_count,
            error_rate=0.0005,
        ),
        ApiEndpointGroup(
            name="Telephony & Live Calls",
            endpoints=[DEFAULT_ENDPOINTS[2]],
            state="HEALTHY",
            request_count=DEFAULT_ENDPOINTS[2].request_count,
            error_rate=0.0,
        ),
        ApiEndpointGroup(
            name="Control Plane & System",
            endpoints=[DEFAULT_ENDPOINTS[4]],
            state="HEALTHY",
            request_count=DEFAULT_ENDPOINTS[4].request_count,
            error_rate=0.0,
        ),
    ]

    return ApiHealthDetail(
        groups=groups,
        updated_at=datetime.now(timezone.utc),
    )
