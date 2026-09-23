import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_role
from app.core.errors import NotFoundException
from app.db.models.reliability import Incident, IncidentEvent
from app.db.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.control_plane.reliability import (
    IncidentEventResponse,
    IncidentResponse,
)
from app.services.control_plane.alert_incident_service import AlertIncidentService

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.get("", response_model=PaginatedResponse[IncidentResponse])
def list_incidents(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    severity: Optional[str] = None,
    status: Optional[str] = None,
    scope: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Incident)
    if "SUPER_ADMIN" not in current_user.roles:
        query = query.where(
            (Incident.organization_id == current_user.organization_id)
            | (Incident.scope == "PLATFORM")
        )

    if severity:
        query = query.where(Incident.severity == severity)
    if status:
        query = query.where(Incident.status == status)
    if scope:
        query = query.where(Incident.scope == scope)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    incidents = db.scalars(
        query.order_by(Incident.started_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = []
    for inc in incidents:
        events = db.scalars(
            select(IncidentEvent).where(IncidentEvent.incident_id == inc.id).order_by(IncidentEvent.timestamp.asc())
        ).all()
        inc_res = IncidentResponse(
            id=inc.id,
            scope=inc.scope,
            organization_id=inc.organization_id,
            title=inc.title,
            description=inc.description,
            severity=inc.severity,
            status=inc.status,
            source=inc.source,
            affected_service_id=inc.affected_service_id,
            correlation_key=inc.correlation_key,
            started_at=inc.started_at,
            resolved_at=inc.resolved_at,
            assigned_to=inc.assigned_to,
            events=[IncidentEventResponse.model_validate(e) for e in events],
            created_at=inc.created_at,
            updated_at=inc.updated_at,
        )
        items.append(inc_res)

    return PaginatedResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{id}", response_model=IncidentResponse)
def get_incident(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inc = db.scalar(select(Incident).where(Incident.id == id))
    if not inc:
        raise NotFoundException(f"Incident {id} not found", code="INCIDENT_NOT_FOUND")

    events = db.scalars(
        select(IncidentEvent).where(IncidentEvent.incident_id == inc.id).order_by(IncidentEvent.timestamp.asc())
    ).all()

    return IncidentResponse(
        id=inc.id,
        scope=inc.scope,
        organization_id=inc.organization_id,
        title=inc.title,
        description=inc.description,
        severity=inc.severity,
        status=inc.status,
        source=inc.source,
        affected_service_id=inc.affected_service_id,
        correlation_key=inc.correlation_key,
        started_at=inc.started_at,
        resolved_at=inc.resolved_at,
        assigned_to=inc.assigned_to,
        events=[IncidentEventResponse.model_validate(e) for e in events],
        created_at=inc.created_at,
        updated_at=inc.updated_at,
    )


@router.post("/{id}/acknowledge", response_model=IncidentResponse)
def acknowledge_incident(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN", "SUPERVISOR")),
):
    inc = AlertIncidentService.acknowledge_incident(db, id, user_id=current_user.id)
    return get_incident(id, db, current_user)


@router.post("/{id}/resolve", response_model=IncidentResponse)
def resolve_incident(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN", "SUPERVISOR")),
):
    inc = AlertIncidentService.resolve_incident(db, id, user_id=current_user.id)
    return get_incident(id, db, current_user)
