from datetime import datetime
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.v1.deps import get_current_user, get_db
from app.db.models.audit import AuditLog
from app.db.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.control_plane.audit import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit Log"])


@router.get("", response_model=PaginatedResponse[AuditLogResponse])
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(AuditLog).options(joinedload(AuditLog.user))
    if "SUPER_ADMIN" not in current_user.roles:
        query = query.where(AuditLog.organization_id == current_user.organization_id)

    if action:
        query = query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if date_from:
        query = query.where(AuditLog.created_at >= date_from)
    if date_to:
        query = query.where(AuditLog.created_at <= date_to)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()


    response_items = []
    for log in items:
        actor_name = log.user.name if log.user else None
        actor_email = log.user.email if log.user else None

        response_items.append(
            AuditLogResponse(
                id=log.id,
                action=log.action,
                actor_id=log.user_id,
                actor_email=actor_email,
                actor_name=actor_name,
                target_id=str(log.entity_id) if log.entity_id else None,
                target_type=log.entity_type,
                occurred_at=log.created_at,
                metadata=log.metadata_json,
            )
        )

    return PaginatedResponse(
        items=response_items,
        page=page,
        page_size=page_size,
        total=total,
    )
