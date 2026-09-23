from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_role
from app.db.models.security_event import SecurityEvent
from app.db.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.control_plane.security import SecurityEventResponse

router = APIRouter(prefix="/security/events", tags=["Security Events"])


@router.get("", response_model=PaginatedResponse[SecurityEventResponse])
def list_security_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    scope: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN")),
):
    query = select(SecurityEvent)
    if "SUPER_ADMIN" not in current_user.roles:
        query = query.where(
            (SecurityEvent.organization_id == current_user.organization_id)
            | (SecurityEvent.scope == "ORGANIZATION")
        )

    if event_type:
        query = query.where(SecurityEvent.event_type == event_type)
    if severity:
        query = query.where(SecurityEvent.severity == severity)
    if scope:
        query = query.where(SecurityEvent.scope == scope)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(SecurityEvent.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[SecurityEventResponse.model_validate(e) for e in items],
        page=page,
        page_size=page_size,
        total=total,
    )
