import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_role
from app.core.errors import NotFoundException
from app.db.models.system_job import SystemJob
from app.db.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.control_plane.job import (
    JobActionRequest,
    JobResponse,
    JobRetryResponse,
)
from app.services.control_plane.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["Job Registry & Control"])


@router.get("", response_model=PaginatedResponse[JobResponse])
def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    queue_id: Optional[uuid.UUID] = None,
    worker_id: Optional[uuid.UUID] = None,
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(SystemJob)
    if "SUPER_ADMIN" not in current_user.roles:
        query = query.where(
            (SystemJob.organization_id == current_user.organization_id)
            | (SystemJob.scope.in_(["PLATFORM", "SERVICE"]))
        )

    if queue_id:
        query = query.where(SystemJob.queue_id == queue_id)
    if worker_id:
        query = query.where(SystemJob.worker_id == worker_id)
    if job_type:
        query = query.where(SystemJob.job_type == job_type)
    if status:
        query = query.where(SystemJob.status == status)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(SystemJob.scheduled_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[JobResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{id}", response_model=JobResponse)
def get_job(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = JobService.get_job(db, id)
    return JobResponse.model_validate(job)


@router.post("/{id}/retry", response_model=JobRetryResponse)
def retry_job(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN", "SUPERVISOR")),
):
    return JobService.retry_job(db, id, requested_by=current_user.id)


@router.post("/{id}/cancel", response_model=JobResponse)
def cancel_job(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN", "SUPERVISOR")),
):
    job = JobService.cancel_job(db, id, requested_by=current_user.id)
    return JobResponse.model_validate(job)


@router.post("/{id}/actions", response_model=JobResponse)
def job_action(
    id: uuid.UUID,
    payload: JobActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN", "SUPERVISOR")),
):
    """Unified job action endpoint supporting retry and cancel."""
    action = payload.action.lower()
    if action == "retry":
        JobService.retry_job(db, id, requested_by=current_user.id)
    elif action == "cancel":
        JobService.cancel_job(db, id, requested_by=current_user.id)
    job = JobService.get_job(db, id)
    return JobResponse.model_validate(job)

