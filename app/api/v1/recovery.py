import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_role
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import PaginatedResponse, SingleResponse
from app.schemas.recovery import (
    DialQueueItemResponse,
    DialQueueReserveRequest,
    DialQueueReserveResponse,
    DncRecordCreate,
    DncRecordResponse,
    RecoveryOutcomeCreate,
    RecoveryOutcomeResponse,
    RecoveryQueueActionRequest,
    RecoveryQueueActionResponse,
    RecoverySummary,
)
from app.services.recovery.dnc import DncService
from app.services.recovery.outcomes import RecoveryOutcomeService
from app.services.recovery.queue import DialQueueService

router = APIRouter(prefix="/recovery", tags=["Recovery Automation"])


# --- Outcomes ---
@router.post("/outcomes", response_model=SingleResponse[RecoveryOutcomeResponse], status_code=status.HTTP_201_CREATED)
def record_outcome(
    data: RecoveryOutcomeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Authoritative outcome recording for calls and recovery interactions."""
    outcome = RecoveryOutcomeService.record_outcome(
        db=db,
        organization_id=current_user.organization_id,
        data=data,
        user_id=current_user.id,
    )
    return SingleResponse(data=RecoveryOutcomeResponse.model_validate(outcome))


@router.get("/outcomes", response_model=PaginatedResponse[RecoveryOutcomeResponse])
def list_outcomes(
    campaign_id: Optional[uuid.UUID] = None,
    account_id: Optional[uuid.UUID] = None,
    outcome_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List recovery outcomes with filters and pagination."""
    items, total = RecoveryOutcomeService.list_outcomes(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
        account_id=account_id,
        outcome_type=outcome_type,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[RecoveryOutcomeResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/summary", response_model=SingleResponse[RecoverySummary])
def get_recovery_summary(
    campaign_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Summary of recovery outcomes and conversion metrics."""
    summary = RecoveryOutcomeService.get_summary(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
    )
    return SingleResponse(data=summary)


# --- Dial Queue ---
@router.get("", response_model=PaginatedResponse[DialQueueItemResponse])
@router.get("/queue", response_model=PaginatedResponse[DialQueueItemResponse])
def list_queue_items(
    campaign_id: Optional[uuid.UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List dial queue items (both /recovery and /recovery/queue)."""
    items, total = DialQueueService.list_queue_items(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[DialQueueItemResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/actions", response_model=SingleResponse[RecoveryQueueActionResponse])
def recovery_queue_action(
    data: RecoveryQueueActionRequest,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Bulk action (pause, resume, close) on recovery queue items."""
    updated = DialQueueService.bulk_action(
        db=db,
        organization_id=current_user.organization_id,
        item_ids=data.item_ids,
        action=data.action,
    )
    return SingleResponse(data=RecoveryQueueActionResponse(updated=updated))


@router.post("/queue/reserve", response_model=SingleResponse[DialQueueReserveResponse])
def reserve_queue_batch(
    data: DialQueueReserveRequest,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Reserve next batch of eligible dial queue items using concurrency-safe locks."""
    items = DialQueueService.reserve_next_batch(
        db=db,
        organization_id=current_user.organization_id,
        worker_id=data.worker_id,
        batch_size=data.batch_size,
        campaign_id=data.campaign_id,
    )
    response_items = [DialQueueItemResponse.model_validate(i) for i in items]
    return SingleResponse(
        data=DialQueueReserveResponse(
            reserved_count=len(response_items),
            items=response_items,
        )
    )


@router.post("/queue/{item_id}/release", response_model=SingleResponse[DialQueueItemResponse])
def release_queue_reservation(
    item_id: uuid.UUID,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Release a reserved queue item back to pending."""
    item = DialQueueService.release_reservation(
        db=db,
        organization_id=current_user.organization_id,
        item_id=item_id,
    )
    return SingleResponse(data=DialQueueItemResponse.model_validate(item))


@router.post("/queue/{item_id}/complete", response_model=SingleResponse[DialQueueItemResponse])
def complete_queue_item(
    item_id: uuid.UUID,
    completion_status: str = Query("completed"),
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Mark a dial queue item as completed or failed."""
    item = DialQueueService.complete_item(
        db=db,
        organization_id=current_user.organization_id,
        item_id=item_id,
        status=completion_status,
    )
    return SingleResponse(data=DialQueueItemResponse.model_validate(item))


# --- DNC Registry ---
@router.post("/dnc", response_model=SingleResponse[DncRecordResponse], status_code=status.HTTP_201_CREATED)
def add_to_dnc(
    data: DncRecordCreate,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Add a phone number to the Do Not Call registry."""
    record = DncService.add_dnc(
        db=db,
        organization_id=current_user.organization_id,
        data=data,
        user_id=current_user.id,
    )
    return SingleResponse(data=DncRecordResponse.model_validate(record))


@router.delete("/dnc/{phone_number}", response_model=SingleResponse[DncRecordResponse])
def remove_from_dnc(
    phone_number: str,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Remove or deactivate a phone number from the DNC registry."""
    record = DncService.remove_dnc(
        db=db,
        organization_id=current_user.organization_id,
        phone_number=phone_number,
        user_id=current_user.id,
    )
    return SingleResponse(data=DncRecordResponse.model_validate(record))


@router.get("/dnc", response_model=PaginatedResponse[DncRecordResponse])
def list_dnc(
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List DNC records with filtering."""
    items, total = DncService.list_dnc(
        db=db,
        organization_id=current_user.organization_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[DncRecordResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )
