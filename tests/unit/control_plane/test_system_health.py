from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy.orm import Session

from app.db.models.ai_infra import AiProvider
from app.db.models.telephony_infra import TelephonyInfrastructure
from app.services.control_plane.health_service import HealthService


def test_system_health_healthy(db: Session):
    health = HealthService.get_system_health(db)
    assert health.overall_status in ("OPERATIONAL", "DEGRADED", "HEALTHY")
    assert len(health.components) >= 8

    api_comp = next((c for c in health.components if c.name == "api"), None)
    assert api_comp is not None
    assert api_comp.status == "HEALTHY"

    db_comp = next((c for c in health.components if c.name == "database"), None)
    assert db_comp is not None
    assert db_comp.status == "HEALTHY"


def test_system_health_degraded_when_telephony_offline(db: Session):
    node = TelephonyInfrastructure(
        scope="PLATFORM",
        type="SIP_TRUNK",
        name="trunk-01",
        status="OFFLINE",
        registration_status="UNREGISTERED",
        capacity=30,
    )
    db.add(node)
    db.commit()

    health = HealthService.get_system_health(db)
    assert health.overall_status == "DEGRADED"

    tel_comp = next((c for c in health.components if c.name == "telephony"), None)
    assert tel_comp is not None
    assert tel_comp.status == "UNAVAILABLE"


def test_readiness_checks(db: Session):
    # Add an AI provider
    p = AiProvider(
        name="test-groq",
        provider_type="LLM",
        scope="PLATFORM",
        priority=1,
        enabled=True,
        status="HEALTHY",
    )
    db.add(p)
    db.commit()

    readiness = HealthService.get_readiness(db)
    assert readiness.ready is True
    assert any(c.name == "database" and c.status == "PASS" for c in readiness.checks)
    assert any(c.name == "ai_gateway" and c.status == "PASS" for c in readiness.checks)
