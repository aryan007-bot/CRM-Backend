from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db
from app.db.models.ai_infra import AiProvider
from app.db.models.call import Call
from app.db.models.call_analysis import CallAnalysis
from app.db.models.dial_queue import DialQueueItem
from app.db.models.automation import FollowUpJob

from app.db.models.reliability import AlertDefinition, Incident
from app.db.models.telephony_infra import TelephonyInfrastructure
from app.db.models.user import User
from app.db.models.worker import WorkerNode
from app.schemas.control_plane.operations import OperationsSnapshotResponse

router = APIRouter(prefix="/operations", tags=["Operations Snapshot"])


@router.get("/snapshot", response_model=OperationsSnapshotResponse)
def get_operations_snapshot(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns aggregated real-time operational metrics across telephony, queues, AI and workers."""
    is_super = "SUPER_ADMIN" in current_user.roles
    org_id = current_user.organization_id

    # 1. Calls
    call_q = select(Call)
    if not is_super:
        call_q = call_q.where(Call.organization_id == org_id)

    active_calls = db.scalar(
        select(func.count(Call.id)).where(Call.status.in_(["ringing", "in_progress", "initiating"]))
    ) or 0
    completed_calls = db.scalar(
        select(func.count(Call.id)).where(Call.status == "completed")
    ) or 0
    failed_calls = db.scalar(
        select(func.count(Call.id)).where(Call.status.in_(["failed", "no_answer", "busy"]))
    ) or 0
    ai_convs = db.scalar(
        select(func.count(Call.id)).where(Call.agent_id.is_not(None))
    ) or 0

    transfers = db.scalar(
        select(func.count(Call.id)).where(Call.status == "transferred")
    ) or 0

    # 2. Queue Depth
    queue_q = select(DialQueueItem).where(DialQueueItem.status == "pending")
    if not is_super:
        queue_q = queue_q.where(DialQueueItem.organization_id == org_id)
    queued_calls = db.scalar(select(func.count()).select_from(queue_q.subquery())) or 0

    # 3. Post-call analysis & Follow-ups
    pending_analysis = db.scalar(
        select(func.count(Call.id)).where(
            Call.status == "completed",
            ~Call.id.in_(select(CallAnalysis.call_id)),
        )
    ) or 0
    pending_followups = db.scalar(
        select(func.count(FollowUpJob.id)).where(FollowUpJob.status == "scheduled")
    ) or 0


    # 4. Workers
    worker_q = select(WorkerNode)
    if not is_super:
        worker_q = worker_q.where(
            (WorkerNode.organization_id == org_id) | (WorkerNode.scope.in_(["PLATFORM", "SERVICE"]))
        )
    workers_total = db.scalar(select(func.count()).select_from(worker_q.subquery())) or 0
    workers_avail = db.scalar(
        select(func.count()).select_from(
            worker_q.where(WorkerNode.status == "HEALTHY").subquery()
        )
    ) or 0

    # 5. Telephony
    telephony_total = db.scalar(select(func.count(TelephonyInfrastructure.id))) or 0
    telephony_avail = db.scalar(
        select(func.count(TelephonyInfrastructure.id)).where(TelephonyInfrastructure.status == "ONLINE")
    ) or 0

    # 6. AI Providers
    ai_total = db.scalar(select(func.count(AiProvider.id))) or 0
    ai_avail = db.scalar(
        select(func.count(AiProvider.id)).where(AiProvider.enabled == True)
    ) or 0

    # 7. Reliability
    incidents_active = db.scalar(
        select(func.count(Incident.id)).where(Incident.status.in_(["OPEN", "INVESTIGATING"]))
    ) or 0
    alerts_unack = db.scalar(
        select(func.count(AlertDefinition.id)).where(AlertDefinition.state == "ACTIVE")
    ) or 0

    return OperationsSnapshotResponse(
        active_calls=active_calls,
        queued_calls=queued_calls,
        completed_calls=completed_calls,
        failed_calls=failed_calls,
        ai_conversations=ai_convs,
        human_transfers=transfers,
        pending_analysis=pending_analysis,
        pending_follow_ups=pending_followups,
        queue_depth=queued_calls,
        workers_available=workers_avail,
        workers_total=workers_total,
        telephony_available=telephony_avail,
        telephony_total=telephony_total,
        ai_providers_available=ai_avail,
        ai_providers_total=ai_total,
        active_incidents=incidents_active,
        unacknowledged_alerts=alerts_unack,
        updated_at=datetime.now(timezone.utc),
    )
