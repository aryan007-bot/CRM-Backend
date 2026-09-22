import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_role
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.automation import (
    FollowUpJobResponse,
    FollowUpJobUpdate,
)
from app.schemas.common import PaginatedResponse, SingleResponse
from app.services.recovery.automation import FollowUpEngine

router = APIRouter(prefix="/follow-ups", tags=["Follow-ups"])


@router.get("", response_model=PaginatedResponse[FollowUpJobResponse])
def list_follow_ups(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List scheduled and dispatched follow-up jobs with status filtering."""
    items, total = FollowUpEngine.list_jobs(
        db=db,
        organization_id=current_user.organization_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[FollowUpJobResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{job_id}", response_model=SingleResponse[FollowUpJobResponse])
def get_follow_up(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details of a specific follow-up job."""
    job = FollowUpEngine.get_job(
        db=db,
        organization_id=current_user.organization_id,
        job_id=job_id,
    )
    return SingleResponse(data=FollowUpJobResponse.model_validate(job))


@router.patch("/{job_id}", response_model=SingleResponse[FollowUpJobResponse])
def update_follow_up(
    job_id: uuid.UUID,
    data: FollowUpJobUpdate,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Update status or reschedule a follow-up job."""
    job = FollowUpEngine.update_job(
        db=db,
        organization_id=current_user.organization_id,
        job_id=job_id,
        status=data.status,
        scheduled_at=data.scheduled_at,
        user_id=current_user.id,
    )
    return SingleResponse(data=FollowUpJobResponse.model_validate(job))


@router.post("/{job_id}/cancel", response_model=SingleResponse[FollowUpJobResponse])
def cancel_follow_up(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Cancel a scheduled follow-up job."""
    job = FollowUpEngine.cancel_job(
        db=db,
        organization_id=current_user.organization_id,
        job_id=job_id,
        user_id=current_user.id,
    )
    return SingleResponse(data=FollowUpJobResponse.model_validate(job))


@router.post("/{job_id}/retry", response_model=SingleResponse[FollowUpJobResponse])
def retry_follow_up(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Re-schedule a failed or cancelled follow-up job for immediate dispatch."""
    job = FollowUpEngine.retry_job(
        db=db,
        organization_id=current_user.organization_id,
        job_id=job_id,
        user_id=current_user.id,
    )
    return SingleResponse(data=FollowUpJobResponse.model_validate(job))
