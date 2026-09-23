import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.reliability import AlertDefinition, Incident, IncidentEvent
from app.services.control_plane.alert_incident_service import AlertIncidentService


def test_alert_evaluation_creates_and_correlates_incident(db: Session):
    alert = AlertDefinition(
        name="high-queue-depth",
        metric="queue_depth",
        operator="GT",
        threshold=50,
        severity="HIGH",
        enabled=True,
        scope="PLATFORM",
        correlation_key="queue:depth:platform",
    )
    db.add(alert)
    db.commit()

    # Trigger metric evaluation with value > threshold
    AlertIncidentService.evaluate_metric(
        db=db,
        metric_name="queue_depth",
        current_value=85.0,
    )

    db.refresh(alert)
    assert alert.state == "ACTIVE"

    incident = db.scalar(select(Incident).where(Incident.correlation_key == "queue:depth:platform"))
    assert incident is not None
    assert incident.status == "OPEN"
    assert incident.severity == "HIGH"

    events = db.scalars(select(IncidentEvent).where(IncidentEvent.incident_id == incident.id)).all()
    assert len(events) >= 1

    # Second evaluation with the same condition must append event, NOT duplicate incident
    AlertIncidentService.evaluate_metric(
        db=db,
        metric_name="queue_depth",
        current_value=90.0,
    )
    all_incidents = db.scalars(select(Incident).where(Incident.correlation_key == "queue:depth:platform")).all()
    assert len(all_incidents) == 1

    events_after = db.scalars(select(IncidentEvent).where(IncidentEvent.incident_id == incident.id)).all()
    assert len(events_after) >= 2


def test_acknowledge_and_resolve_incident(db: Session):
    user_id = uuid.uuid4()
    incident = Incident(
        scope="PLATFORM",
        title="Database Latency Spike",
        description="P95 latency exceeded 200ms",
        severity="MEDIUM",
        status="OPEN",
        source="ALERT_ENGINE",
        correlation_key="db:latency:platform",
    )
    db.add(incident)
    db.commit()

    # Acknowledge
    ack = AlertIncidentService.acknowledge_incident(db, incident.id, user_id=user_id)
    assert ack.status == "INVESTIGATING"
    assert ack.assigned_to == user_id

    # Resolve
    res = AlertIncidentService.resolve_incident(db, incident.id, user_id=user_id)
    assert res.status == "RESOLVED"
    assert res.resolved_at is not None
