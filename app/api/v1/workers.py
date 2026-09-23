import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_role
from app.core.errors import NotFoundException
from app.db.models.user import User
from app.db.models.worker import WorkerNode
from app.schemas.common import PaginatedResponse
from app.schemas.control_plane.worker import (
    WorkerActionRequest,
    WorkerCommandResponse,
    WorkerHeartbeatRequest,
    WorkerResponse,
)
from app.services.control_plane.worker_service import WorkerService

router = APIRouter(prefix="/workers", tags=["Worker Registry & Management"])


@router.get("", response_model=PaginatedResponse[WorkerResponse])
def list_workers(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    scope: Optional[str] = None,
    worker_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(WorkerNode)
    if "SUPER_ADMIN" not in current_user.roles:
        query = query.where(
            (WorkerNode.organization_id == current_user.organization_id)
            | (WorkerNode.scope.in_(["PLATFORM", "SERVICE"]))
        )

    if scope:
        query = query.where(WorkerNode.scope == scope)
    if worker_type:
        query = query.where(WorkerNode.worker_type == worker_type)
    if status:
        query = query.where(WorkerNode.status == status)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()

    return PaginatedResponse(
        items=[WorkerResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{id}", response_model=WorkerResponse)
def get_worker(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    worker = db.scalar(select(WorkerNode).where(WorkerNode.id == id))
    if not worker:
        raise NotFoundException(f"Worker {id} not found", code="WORKER_NOT_FOUND")
    return WorkerResponse.model_validate(worker)


@router.post("/heartbeat", response_model=WorkerResponse)
def worker_heartbeat(
    payload: WorkerHeartbeatRequest,
    db: Session = Depends(get_db),
):
    """Heartbeat endpoint for active workers."""
    worker = WorkerService.record_heartbeat(
        db=db,
        worker_id=payload.worker_id,
        status=payload.status,
        active_jobs=payload.active_jobs,
        concurrency=payload.concurrency,
        version=payload.version,
    )
    return WorkerResponse.model_validate(worker)


@router.post("/{id}/drain", response_model=WorkerCommandResponse)
def drain_worker(
    id: uuid.UUID,
    payload: Optional[WorkerActionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN")),
):
    idempotency_key = payload.idempotency_key if payload else None
    cmd = WorkerService.dispatch_command(
        db=db,
        worker_id=id,
        command="DRAIN",
        requested_by=current_user.id,
        idempotency_key=idempotency_key,
    )
    return WorkerCommandResponse.model_validate(cmd)


@router.post("/{id}/resume", response_model=WorkerCommandResponse)
def resume_worker(
    id: uuid.UUID,
    payload: Optional[WorkerActionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN")),
):
    idempotency_key = payload.idempotency_key if payload else None
    cmd = WorkerService.dispatch_command(
        db=db,
        worker_id=id,
        command="RESUME",
        requested_by=current_user.id,
        idempotency_key=idempotency_key,
    )
    return WorkerCommandResponse.model_validate(cmd)


@router.post("/{id}/restart", response_model=WorkerCommandResponse)
def restart_worker(
    id: uuid.UUID,
    payload: Optional[WorkerActionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN")),
):
    idempotency_key = payload.idempotency_key if payload else None
    cmd = WorkerService.dispatch_command(
        db=db,
        worker_id=id,
        command="RESTART",
        requested_by=current_user.id,
        idempotency_key=idempotency_key,
    )
    return WorkerCommandResponse.model_validate(cmd)


@router.post("/{id}/disable", response_model=WorkerCommandResponse)
def disable_worker(
    id: uuid.UUID,
    payload: Optional[WorkerActionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN")),
):
    idempotency_key = payload.idempotency_key if payload else None
    cmd = WorkerService.dispatch_command(
        db=db,
        worker_id=id,
        command="DISABLE",
        requested_by=current_user.id,
        idempotency_key=idempotency_key,
    )
    return WorkerCommandResponse.model_validate(cmd)


@router.post("/{id}/actions", response_model=WorkerResponse)
def worker_action(
    id: uuid.UUID,
    payload: WorkerActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN")),
):
    """Unified worker actions endpoint supporting drain, resume, restart, and disable."""
    worker = db.scalar(select(WorkerNode).where(WorkerNode.id == id))
    if not worker:
        raise NotFoundException(f"Worker {id} not found", code="WORKER_NOT_FOUND")

    action = (payload.action or "restart").upper()
    valid_actions = {"DRAIN", "RESUME", "RESTART", "DISABLE"}
    if action in valid_actions:
        WorkerService.dispatch_command(
            db=db,
            worker_id=id,
            command=action,
            requested_by=current_user.id,
            idempotency_key=payload.idempotency_key,
        )

    db.refresh(worker)
    return WorkerResponse.model_validate(worker)

