from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db
from app.db.models.security_event import OperationalEvent
from app.db.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.control_plane.logs import LogEntryResponse

router = APIRouter(prefix="/logs", tags=["System Logs Stream"])


@router.get("", response_model=PaginatedResponse[LogEntryResponse])
def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    service: Optional[str] = None,
    level: Optional[str] = None,
    request_id: Optional[str] = None,
    query: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(OperationalEvent)
    if "SUPER_ADMIN" not in current_user.roles:
        stmt = stmt.where(
            (OperationalEvent.organization_id == current_user.organization_id)
            | (OperationalEvent.scope == "PLATFORM")
        )

    if service:
        stmt = stmt.where(OperationalEvent.entity_type == service)
    if level:
        stmt = stmt.where(OperationalEvent.severity == level.upper())
    if query:
        stmt = stmt.where(OperationalEvent.message.ilike(f"%{query}%"))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(OperationalEvent.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    entries = []
    for item in items:
        # Map severity to standard log level
        sev = (item.severity or "INFO").upper()
        if sev == "WARNING":
            sev = "WARN"
        elif sev not in ("DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"):
            sev = "INFO"

        entries.append(
            LogEntryResponse(
                id=str(item.id),
                timestamp=item.timestamp,
                level=sev,
                service=item.entity_type or "system",
                message=item.message or item.event_type,
                request_id=request_id or (str(item.entity_id) if item.entity_id else None),
                user_id=None,
                metadata=item.payload_safe,
            )
        )

    return PaginatedResponse(
        items=entries,
        page=page,
        page_size=page_size,
        total=total,
    )
