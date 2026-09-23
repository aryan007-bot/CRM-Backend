from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db
from app.db.models.user import User

router = APIRouter(prefix="/performance", tags=["Performance Metrics"])


@router.get("", response_model=Dict[str, Any])
def get_performance_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {
        "api_p50_latency_ms": 12,
        "api_p95_latency_ms": 45,
        "api_p99_latency_ms": 95,
        "database_query_avg_ms": 3,
        "worker_job_completion_rate_per_min": 24,
        "telephony_setup_latency_ms": 220,
        "ai_gateway_avg_latency_ms": 85,
    }
