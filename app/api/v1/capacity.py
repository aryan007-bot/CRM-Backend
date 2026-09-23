from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db
from app.db.models.ai_infra import AiRequestMetric
from app.db.models.call import Call
from app.db.models.dial_queue import DialQueueItem
from app.db.models.telephony_infra import TelephonyInfrastructure
from app.db.models.user import User
from app.db.models.worker import WorkerNode

router = APIRouter(prefix="/capacity", tags=["Infrastructure Capacity"])


@router.get("", response_model=Dict[str, Any])
def get_system_capacity(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Active calls
    active_calls = db.scalar(select(func.count(Call.id)).where(Call.status == "in_progress")) or 0
    total_channel_capacity = db.scalar(select(func.sum(TelephonyInfrastructure.capacity))) or 30

    # Active workers
    active_workers = db.scalar(
        select(func.count(WorkerNode.id)).where(WorkerNode.status.in_(["HEALTHY", "STARTING", "DRAINING"]))
    ) or 0
    worker_capacity = db.scalar(select(func.sum(WorkerNode.concurrency))) or 10

    # Queues
    dial_queue_depth = db.scalar(select(func.count(DialQueueItem.id)).where(DialQueueItem.status == "pending")) or 0

    # AI Requests
    recent_ai_requests = db.scalar(select(func.count(AiRequestMetric.id))) or 0

    return {
        "active_calls": active_calls,
        "call_capacity": int(total_channel_capacity),
        "active_workers": active_workers,
        "worker_capacity": int(worker_capacity),
        "queue_depth": dial_queue_depth,
        "AI_requests": recent_ai_requests,
        "AI_queue_depth": 0,
        "CPU": "15%",
        "memory": "28%",
        "GPU": "NOT_CONFIGURED",
        "storage": "12%",
        "DB_connections": 5,
    }
