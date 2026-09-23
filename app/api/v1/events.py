from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db
from app.db.models.security_event import OperationalEvent
from app.db.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.control_plane.security import OperationalEventResponse

router = APIRouter(prefix="/events", tags=["Operational Events"])


@router.get("", response_model=PaginatedResponse[OperationalEventResponse])
def list_operational_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    scope: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(OperationalEvent)
    if "SUPER_ADMIN" not in current_user.roles:
        query = query.where(
            (OperationalEvent.organization_id == current_user.organization_id)
            | (OperationalEvent.scope == "PLATFORM")
        )

    if event_type:
        query = query.where(OperationalEvent.event_type == event_type)
    if severity:
        query = query.where(OperationalEvent.severity == severity)
    if scope:
        query = query.where(OperationalEvent.scope == scope)
    if entity_type:
        query = query.where(OperationalEvent.entity_type == entity_type)
    if entity_id:
        query = query.where(OperationalEvent.entity_id == entity_id)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(OperationalEvent.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[OperationalEventResponse.model_validate(e) for e in items],
        page=page,
        page_size=page_size,
        total=total,
    )
