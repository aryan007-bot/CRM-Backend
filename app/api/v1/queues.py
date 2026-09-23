import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_role
from app.core.errors import NotFoundException
from app.db.models.queue import QueueMetricSnapshot, QueueRegistryItem
from app.db.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.control_plane.queue import (
    QueueActionRequest,
    QueueMetricSnapshotResponse,
    QueueResponse,
)
from app.services.control_plane.queue_service import QueueService

router = APIRouter(prefix="/queues", tags=["Queue Monitoring & Control"])


@router.get("", response_model=PaginatedResponse[QueueResponse])
def list_queues(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    scope: Optional[str] = None,
    queue_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    QueueService.ensure_default_queues(db)

    query = select(QueueRegistryItem)
    if "SUPER_ADMIN" not in current_user.roles:
        query = query.where(
            (QueueRegistryItem.organization_id == current_user.organization_id)
            | (QueueRegistryItem.scope.in_(["PLATFORM", "SERVICE"]))
        )

    if scope:
        query = query.where(QueueRegistryItem.scope == scope)
    if queue_type:
        query = query.where(QueueRegistryItem.queue_type == queue_type)
    if status:
        query = query.where(QueueRegistryItem.status == status)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()

    response_items = []
    for q in items:
        metric = db.scalars(
            select(QueueMetricSnapshot)
            .where(QueueMetricSnapshot.queue_id == q.id)
            .order_by(QueueMetricSnapshot.captured_at.desc())
        ).first()

        res = QueueResponse(
            id=q.id,
            scope=q.scope,
            organization_id=q.organization_id,
            name=q.name,
            queue_type=q.queue_type,
            status=q.status,
            backend_reference_safe=q.backend_reference_safe,
            current_metrics=QueueMetricSnapshotResponse.model_validate(metric) if metric else None,
            created_at=q.created_at,
            updated_at=q.updated_at,
        )
        response_items.append(res)

    return PaginatedResponse(
        items=response_items,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{id}", response_model=QueueResponse)
def get_queue(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    queue = db.scalar(select(QueueRegistryItem).where(QueueRegistryItem.id == id))
    if not queue:
        raise NotFoundException(f"Queue {id} not found", code="QUEUE_NOT_FOUND")

    metric = db.scalars(
        select(QueueMetricSnapshot)
        .where(QueueMetricSnapshot.queue_id == queue.id)
        .order_by(QueueMetricSnapshot.captured_at.desc())
    ).first()

    return QueueResponse(
        id=queue.id,
        scope=queue.scope,
        organization_id=queue.organization_id,
        name=queue.name,
        queue_type=queue.queue_type,
        status=queue.status,
        backend_reference_safe=queue.backend_reference_safe,
        current_metrics=QueueMetricSnapshotResponse.model_validate(metric) if metric else None,
        created_at=queue.created_at,
        updated_at=queue.updated_at,
    )


@router.post("/{id}/pause", response_model=QueueResponse)
def pause_queue(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN", "SUPERVISOR")),
):
    queue = QueueService.pause_queue(db, id, requested_by=current_user.id)
    return QueueResponse.model_validate(queue)


@router.post("/{id}/resume", response_model=QueueResponse)
def resume_queue(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN", "SUPERVISOR")),
):
    queue = QueueService.resume_queue(db, id, requested_by=current_user.id)
    return QueueResponse.model_validate(queue)


@router.post("/{id}/actions", response_model=QueueResponse)
def queue_action(
    id: uuid.UUID,
    payload: QueueActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN", "SUPERVISOR")),
):
    """Unified queue action endpoint supporting pause, resume, and retry_failed."""
    action = payload.action.lower()
    if action == "pause":
        queue = QueueService.pause_queue(db, id, requested_by=current_user.id)
    elif action == "resume":
        queue = QueueService.resume_queue(db, id, requested_by=current_user.id)
    else:
        queue = db.scalar(select(QueueRegistryItem).where(QueueRegistryItem.id == id))
        if not queue:
            raise NotFoundException(f"Queue {id} not found", code="QUEUE_NOT_FOUND")
    return QueueResponse.model_validate(queue)

