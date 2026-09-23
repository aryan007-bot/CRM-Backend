from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundException
from app.db.models.audit import AuditLog
from app.db.models.reliability import AlertDefinition, Incident, IncidentEvent
from app.services.control_plane.event_bus import event_bus


class AlertIncidentService:
    """Evaluates metrics against alert rules, manages incident state machines, and correlates events."""

    @staticmethod
    def evaluate_metric(
        db: Session,
        metric_name: str,
        current_value: float,
        scope: str = "PLATFORM",
        organization_id: Optional[uuid.UUID] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        alerts = db.scalars(
            select(AlertDefinition).where(
                AlertDefinition.metric == metric_name,
                AlertDefinition.enabled == True,
            )
        ).all()

        for alert in alerts:
            triggered = False
            op = alert.operator.upper()
            th = alert.threshold

            if op == "GT" and current_value > th:
                triggered = True
            elif op == "GTE" and current_value >= th:
                triggered = True
            elif op == "LT" and current_value < th:
                triggered = True
            elif op == "LTE" and current_value <= th:
                triggered = True
            elif op == "EQ" and current_value == th:
                triggered = True

            now = datetime.now(timezone.utc)
            if triggered:
                alert.state = "ACTIVE"
                alert.last_triggered_at = now

                # Correlate incident to avoid alert storms
                correlation_key = alert.correlation_key or f"{alert.name}:{metric_name}:{alert.scope}"
                existing_incident = db.scalar(
                    select(Incident).where(
                        Incident.correlation_key == correlation_key,
                        Incident.status.in_(["OPEN", "INVESTIGATING"]),
                    )
                )

                if existing_incident:
                    # Append event to existing incident
                    event = IncidentEvent(
                        incident_id=existing_incident.id,
                        event_type="ALERT_TRIGGERED",
                        message=f"Alert {alert.name} triggered with value {current_value} (threshold {th})",
                        source="ALERT_ENGINE",
                        timestamp=now,
                        metadata_safe={"metric": metric_name, "value": current_value, "threshold": th},
                    )
                    db.add(event)
                else:
                    # Create new incident
                    incident = Incident(
                        scope=alert.scope,
                        organization_id=alert.organization_id or organization_id,
                        title=f"Incident: {alert.name} threshold breached",
                        description=f"Metric {metric_name} reached {current_value}, exceeding threshold of {th} ({op}).",
                        severity=alert.severity,
                        status="OPEN",
                        source="ALERT_ENGINE",
                        correlation_key=correlation_key,
                        started_at=now,
                    )
                    db.add(incident)
                    db.flush()

                    init_event = IncidentEvent(
                        incident_id=incident.id,
                        event_type="DETECTED",
                        message="Incident opened automatically from alert breach",
                        source="ALERT_ENGINE",
                        timestamp=now,
                        metadata_safe={"metric": metric_name, "value": current_value},
                    )
                    db.add(init_event)

                    event_bus.emit_operational_event(
                        db=db,
                        event_type="incident.created",
                        scope=incident.scope,
                        organization_id=incident.organization_id,
                        entity_type="incident",
                        entity_id=str(incident.id),
                        severity=incident.severity,
                        message=incident.title,
                    )
            else:
                if alert.state == "ACTIVE":
                    alert.state = "RESOLVED"

        db.flush()

    @staticmethod
    def acknowledge_alert(db: Session, alert_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> AlertDefinition:
        alert = db.scalar(select(AlertDefinition).where(AlertDefinition.id == alert_id))
        if not alert:
            raise NotFoundException(f"Alert {alert_id} not found", code="ALERT_NOT_FOUND")

        alert.state = "ACKNOWLEDGED"
        audit = AuditLog(
            organization_id=alert.organization_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
            user_id=user_id,
            action="ALERT_ACKNOWLEDGED",
            entity_type="alert",
            entity_id=alert.id,
            metadata_json={"state": "ACKNOWLEDGED"},
        )
        db.add(audit)
        db.commit()
        return alert

    @staticmethod
    def resolve_alert(db: Session, alert_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> AlertDefinition:
        alert = db.scalar(select(AlertDefinition).where(AlertDefinition.id == alert_id))
        if not alert:
            raise NotFoundException(f"Alert {alert_id} not found", code="ALERT_NOT_FOUND")

        alert.state = "RESOLVED"
        audit = AuditLog(
            organization_id=alert.organization_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
            user_id=user_id,
            action="ALERT_RESOLVED",
            entity_type="alert",
            entity_id=alert.id,
            metadata_json={"state": "RESOLVED"},
        )
        db.add(audit)
        db.commit()
        return alert


    @staticmethod
    def acknowledge_incident(db: Session, incident_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> Incident:
        incident = db.scalar(select(Incident).where(Incident.id == incident_id))
        if not incident:
            raise NotFoundException(f"Incident {incident_id} not found", code="INCIDENT_NOT_FOUND")

        incident.status = "INVESTIGATING"
        incident.assigned_to = user_id
        now = datetime.now(timezone.utc)

        event = IncidentEvent(
            incident_id=incident.id,
            event_type="ACKNOWLEDGED",
            message=f"Incident acknowledged and assigned to user {user_id}",
            source="USER",
            timestamp=now,
        )
        db.add(event)

        audit = AuditLog(
            organization_id=incident.organization_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
            user_id=user_id,
            action="INCIDENT_ACKNOWLEDGED",
            entity_type="incident",
            entity_id=incident.id,
            metadata_json={"status": "INVESTIGATING", "assigned_to": str(user_id) if user_id else None},
        )
        db.add(audit)
        db.commit()
        return incident

    @staticmethod
    def resolve_incident(db: Session, incident_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> Incident:
        incident = db.scalar(select(Incident).where(Incident.id == incident_id))
        if not incident:
            raise NotFoundException(f"Incident {incident_id} not found", code="INCIDENT_NOT_FOUND")

        now = datetime.now(timezone.utc)
        incident.status = "RESOLVED"
        incident.resolved_at = now

        event = IncidentEvent(
            incident_id=incident.id,
            event_type="RESOLVED",
            message="Incident marked as resolved",
            source="USER",
            timestamp=now,
        )
        db.add(event)

        audit = AuditLog(
            organization_id=incident.organization_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
            user_id=user_id,
            action="INCIDENT_RESOLVED",
            entity_type="incident",
            entity_id=incident.id,
            metadata_json={"status": "RESOLVED", "resolved_at": now.isoformat()},
        )
        db.add(audit)

        event_bus.emit_operational_event(
            db=db,
            event_type="incident.resolved",
            scope=incident.scope,
            organization_id=incident.organization_id,
            entity_type="incident",
            entity_id=str(incident.id),
            severity="INFO",
            message=f"Incident {incident.title} resolved",
        )
        db.commit()
        return incident

