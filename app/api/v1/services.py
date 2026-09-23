import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_role
from app.core.errors import NotFoundException
from app.db.models.service import PlatformService, ServiceHealthLog
from app.db.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.control_plane.service import ServiceHealthLogResponse, ServiceResponse

router = APIRouter(prefix="/services", tags=["Service Registry & Health"])


@router.get("", response_model=PaginatedResponse[ServiceResponse])
def list_services(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    scope: Optional[str] = None,
    service_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(PlatformService)
    if "SUPER_ADMIN" not in current_user.roles:
        query = query.where(
            (PlatformService.organization_id == current_user.organization_id)
            | (PlatformService.scope == "PLATFORM")
        )

    if scope:
        query = query.where(PlatformService.scope == scope)
    if service_type:
        query = query.where(PlatformService.service_type == service_type)
    if status:
        query = query.where(PlatformService.status == status)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()

    return PaginatedResponse(
        items=[ServiceResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{id}", response_model=ServiceResponse)
def get_service(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = db.scalar(select(PlatformService).where(PlatformService.id == id))
    if not service:
        raise NotFoundException(f"Service {id} not found", code="SERVICE_NOT_FOUND")
    return ServiceResponse.model_validate(service)


@router.get("/{id}/health", response_model=List[ServiceHealthLogResponse])
def get_service_health(
    id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = db.scalar(select(PlatformService).where(PlatformService.id == id))
    if not service:
        raise NotFoundException(f"Service {id} not found", code="SERVICE_NOT_FOUND")

    logs = db.scalars(
        select(ServiceHealthLog)
        .where(ServiceHealthLog.service_id == id)
        .order_by(ServiceHealthLog.checked_at.desc())
        .limit(limit)
    ).all()

    return [ServiceHealthLogResponse.model_validate(log) for log in logs]
