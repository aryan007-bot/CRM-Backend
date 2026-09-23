import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_role
from app.core.errors import NotFoundException
from app.db.models.audit import AuditLog
from app.db.models.reliability import AlertDefinition
from app.db.models.user import User
from app.schemas.control_plane.reliability import (
    AlertActionRequest,
    AlertCreate,
    AlertResponse,
    AlertUpdate,
)
from app.services.control_plane.alert_incident_service import AlertIncidentService

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=List[AlertResponse])
def list_alerts(
    state: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(AlertDefinition)
    if "SUPER_ADMIN" not in current_user.roles:
        query = query.where(
            (AlertDefinition.organization_id == current_user.organization_id)
            | (AlertDefinition.scope == "PLATFORM")
        )

    if state:
        query = query.where(AlertDefinition.state == state)
    if severity:
        query = query.where(AlertDefinition.severity == severity)

    alerts = db.scalars(query).all()
    return [AlertResponse.model_validate(a) for a in alerts]


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
def create_alert(
    payload: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN")),
):
    alert = AlertDefinition(
        name=payload.name,
        metric=payload.metric,
        operator=payload.operator,
        threshold=payload.threshold,
        window_seconds=payload.window_seconds,
        severity=payload.severity,
        enabled=payload.enabled,
        scope=payload.scope,
        organization_id=payload.organization_id,
        state="RESOLVED",
        correlation_key=f"{payload.name}:{payload.metric}:{payload.scope}",
    )
    db.add(alert)
    db.flush()

    audit = AuditLog(
        organization_id=payload.organization_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
        user_id=current_user.id,
        action="ALERT_CREATED",
        entity_type="alert",
        entity_id=alert.id,
        metadata_json={"name": alert.name, "metric": alert.metric},
    )
    db.add(audit)
    db.commit()

    return AlertResponse.model_validate(alert)


@router.patch("/{id}", response_model=AlertResponse)
def update_alert(
    id: uuid.UUID,
    payload: AlertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN")),
):
    alert = db.scalar(select(AlertDefinition).where(AlertDefinition.id == id))
    if not alert:
        raise NotFoundException(f"Alert {id} not found", code="ALERT_NOT_FOUND")

    if payload.name is not None:
        alert.name = payload.name
    if payload.metric is not None:
        alert.metric = payload.metric
    if payload.operator is not None:
        alert.operator = payload.operator
    if payload.threshold is not None:
        alert.threshold = payload.threshold
    if payload.window_seconds is not None:
        alert.window_seconds = payload.window_seconds
    if payload.severity is not None:
        alert.severity = payload.severity
    if payload.enabled is not None:
        alert.enabled = payload.enabled

    db.commit()
    return AlertResponse.model_validate(alert)


@router.post("/{id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN", "SUPERVISOR")),
):
    alert = AlertIncidentService.acknowledge_alert(db, id, user_id=current_user.id)
    return AlertResponse.model_validate(alert)


@router.post("/{id}/enable", response_model=AlertResponse)
def enable_alert(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN")),
):
    alert = db.scalar(select(AlertDefinition).where(AlertDefinition.id == id))
    if not alert:
        raise NotFoundException(f"Alert {id} not found", code="ALERT_NOT_FOUND")
    alert.enabled = True
    db.commit()
    return AlertResponse.model_validate(alert)


@router.get("/{id}", response_model=AlertResponse)
def get_alert(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.scalar(select(AlertDefinition).where(AlertDefinition.id == id))
    if not alert:
        raise NotFoundException(f"Alert {id} not found", code="ALERT_NOT_FOUND")
    return AlertResponse.model_validate(alert)


@router.post("/{id}/disable", response_model=AlertResponse)
def disable_alert(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN")),
):
    alert = db.scalar(select(AlertDefinition).where(AlertDefinition.id == id))
    if not alert:
        raise NotFoundException(f"Alert {id} not found", code="ALERT_NOT_FOUND")
    alert.enabled = False
    alert.state = "DISABLED"
    db.commit()
    return AlertResponse.model_validate(alert)


@router.post("/{id}/resolve", response_model=AlertResponse)
def resolve_alert(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN", "SUPERVISOR")),
):
    alert = AlertIncidentService.resolve_alert(db, id, user_id=current_user.id)
    return AlertResponse.model_validate(alert)


@router.post("/{id}/actions", response_model=AlertResponse)
def alert_action(
    id: uuid.UUID,
    payload: AlertActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN", "SUPERVISOR")),
):
    """Unified alert actions endpoint supporting acknowledge, resolve, and disable."""
    action = payload.action.lower()
    if action == "acknowledge":
        alert = AlertIncidentService.acknowledge_alert(db, id, user_id=current_user.id)
    elif action == "resolve":
        alert = AlertIncidentService.resolve_alert(db, id, user_id=current_user.id)
    elif action == "disable":
        alert = db.scalar(select(AlertDefinition).where(AlertDefinition.id == id))
        if not alert:
            raise NotFoundException(f"Alert {id} not found", code="ALERT_NOT_FOUND")
        alert.enabled = False
        alert.state = "DISABLED"
        db.commit()
    else:
        alert = db.scalar(select(AlertDefinition).where(AlertDefinition.id == id))
        if not alert:
            raise NotFoundException(f"Alert {id} not found", code="ALERT_NOT_FOUND")
    return AlertResponse.model_validate(alert)


