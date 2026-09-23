import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_role
from app.core.errors import NotFoundException
from app.db.models.deployment import DeploymentRecord
from app.db.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.control_plane.deployment import (
    DeploymentCreate,
    DeploymentResponse,
    DeploymentRollbackRequest,
)
from app.services.control_plane.deployment_service import DeploymentService

router = APIRouter(prefix="/deployments", tags=["Deployments"])


@router.get("", response_model=PaginatedResponse[DeploymentResponse])
def list_deployments(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    environment_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(DeploymentRecord)
    if environment_id:
        query = query.where(DeploymentRecord.environment_id == environment_id)
    if status:
        query = query.where(DeploymentRecord.status == status)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(DeploymentRecord.started_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[DeploymentResponse.model_validate(d) for d in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{id}", response_model=DeploymentResponse)
def get_deployment(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dep = db.scalar(select(DeploymentRecord).where(DeploymentRecord.id == id))
    if not dep:
        raise NotFoundException(f"Deployment {id} not found", code="DEPLOYMENT_NOT_FOUND")
    return DeploymentResponse.model_validate(dep)


@router.post("", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
def trigger_deployment(
    payload: DeploymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN")),
):
    return DeploymentService.trigger_deployment(
        db=db,
        environment_id=payload.environment_id,
        version=payload.version,
        commit_sha=payload.commit_sha,
        deployed_by=current_user.id,
    )


@router.post("/{id}/rollback", response_model=DeploymentResponse)
def rollback_deployment(
    id: uuid.UUID,
    payload: Optional[DeploymentRollbackRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN")),
):
    target_version = payload.target_version if payload else None
    return DeploymentService.rollback_deployment(
        db=db,
        deployment_id=id,
        target_version=target_version,
        user_id=current_user.id,
    )
