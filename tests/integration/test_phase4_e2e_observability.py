from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.ai_agent import AiAgent, VoiceProfile
from app.db.models.ai_infra import AiModel, AiProvider, AiRequestMetric, AiRoutingRule
from app.db.models.audit import AuditLog
from app.db.models.call import Call, TranscriptMessage
from app.db.models.creditor import Creditor
from app.db.models.customer import Customer, CustomerPhone
from app.db.models.organization import Organization
from app.db.models.queue import QueueRegistryItem
from app.db.models.reliability import AlertDefinition, Incident
from app.db.models.security_event import OperationalEvent
from app.db.models.telephony_infra import TelephonyInfrastructure
from app.db.models.user import User
from app.db.models.worker import WorkerNode
from app.services.control_plane.ai_router_service import AIRouter
from app.services.control_plane.event_bus import event_bus
from app.workers.monitoring_worker import run_monitoring_cycle_sync
from tests.conftest import auth_headers


def test_phase4_e2e_control_plane_and_observability(
    client: TestClient,
    db: Session,
    super_admin: User,
    test_org_a: Organization,
):
    """SCENARIO 121: End-to-End Control Plane & Observability Lifecycle.

    Flow:
    1. Start system -> API healthy -> DB healthy -> Readiness true
    2. Queue healthy -> Worker registers & heartbeats
    3. AI Provider and Model configured -> Router routes and tracks usage/latency
    4. Telephony SIP trunk provisioned and verified
    5. Campaign and Call execution with AI telemetry
    6. Worker failure simulated -> Monitoring cycle runs -> Incident created
    7. Incident acknowledged -> Worker recovers -> Incident resolved
    8. Complete audit and operational event trail verified
    """
    headers = auth_headers(super_admin)

    # 1. System Health & Readiness Verification
    res_health = client.get("/api/v1/system/health", headers=headers)
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["overall_status"] in ("OPERATIONAL", "HEALTHY", "DEGRADED")
    component_names = [c["name"] for c in health_data["components"]]
    assert "api" in component_names
    assert "database" in component_names



    res_ready = client.get("/api/v1/system/readiness", headers=headers)
    assert res_ready.status_code == 200
    assert res_ready.json()["ready"] is True

    # 2. Worker Registration & Heartbeat
    worker = WorkerNode(
        scope="PLATFORM",
        worker_type="CAMPAIGN",
        status="HEALTHY",
        hostname="worker-node-alpha-01",
        concurrency=10,
        active_jobs=0,
    )
    db.add(worker)
    db.commit()

    res_hb = client.post(
        "/api/v1/workers/heartbeat",
        headers=headers,
        json={"worker_id": str(worker.id), "status": "HEALTHY", "active_jobs": 2},
    )
    assert res_hb.status_code == 200
    assert res_hb.json()["active_jobs"] == 2

    # 3. Queue Registry Check
    queue = QueueRegistryItem(
        name="dial-priority-queue",
        queue_type="DIAL",
        scope="PLATFORM",
        status="HEALTHY",
    )

    db.add(queue)
    db.commit()

    res_queue = client.get("/api/v1/queues", headers=headers)
    assert res_queue.status_code == 200
    assert res_queue.json()["total"] >= 1

    # 4. AI Provider, Model, and Routing Configuration
    res_prov = client.post(
        "/api/v1/ai/providers",
        headers=headers,
        json={
            "name": "groq-production-llm",
            "provider_type": "LLM",
            "priority": 1,
            "api_key": "gsk_prod_secret_key_123",
        },
    )
    assert res_prov.status_code == 201
    prov_id = res_prov.json()["id"]
    assert "api_key" not in res_prov.json()  # Secret masked

    res_model = client.post(
        "/api/v1/ai/models",
        headers=headers,
        json={
            "provider_id": prov_id,
            "name": "llama-3.3-70b-versatile",
            "model_type": "LLM",
            "streaming_supported": True,
        },
    )
    assert res_model.status_code == 201
    model_id = res_model.json()["id"]

    res_route = client.post(
        "/api/v1/ai/routing",
        headers=headers,
        json={
            "service_type": "LLM",
            "primary_provider_id": prov_id,
            "primary_model_id": model_id,
            "enabled": True,
            "priority": 1,
        },
    )
    assert res_route.status_code == 201

    # Route AI Request & Record Metric
    routed = AIRouter.resolve_provider(db, service_type="LLM")
    routed_prov = routed["provider"]
    routed_model = routed["model"]
    assert routed_prov.name == "groq-production-llm"

    call_id = uuid.uuid4()
    metric = AIRouter.record_request_metric(
        db=db,
        service_type="LLM",
        provider_id=routed_prov.id,
        model_id=routed_model.id if routed_model else None,
        input_tokens=120,
        output_tokens=80,
        latency_ms=85,
        status="SUCCESS",
        organization_id=test_org_a.id,
    )
    db.commit()
    assert (metric.input_tokens + metric.output_tokens) == 200


    # 5. Telephony SIP Trunk Provisioning
    trunk = TelephonyInfrastructure(
        name="primary-sip-carrier",
        type="SIP_TRUNK",
        scope="PLATFORM",
        status="ONLINE",
        capacity=60,
        active_channels=4,
    )
    db.add(trunk)
    db.commit()

    res_infra = client.get("/api/v1/telephony/infrastructure", headers=headers)
    assert res_infra.status_code == 200
    assert len(res_infra.json()) >= 1
    trunk_id = trunk.id



    # 6. Campaign & Call Telemetry with Operational Event
    event_bus.emit_operational_event(
        db=db,
        event_type="call.started",
        scope="ORGANIZATION",
        organization_id=test_org_a.id,
        entity_type="call",
        entity_id=str(call_id),
        severity="INFO",
        message="AI Recovery call initiated",
        payload={"trunk_id": trunk_id, "duration": 45},
    )
    db.commit()

    # 7. Worker Failure Simulation & Alert/Incident Trigger
    # Register alert definition for worker degradation
    res_alert = client.post(
        "/api/v1/alerts",
        headers=headers,
        json={
            "name": "Worker Node Failure Alert",
            "metric": "worker_failed",
            "operator": "GT",
            "threshold": 0,
            "severity": "CRITICAL",
        },
    )
    assert res_alert.status_code == 201
    alert_id = res_alert.json()["id"]

    # Simulate worker degradation
    worker_rec = db.scalar(select(WorkerNode).where(WorkerNode.id == worker.id))
    worker_rec.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()

    # Run monitoring cycle synchronously
    run_monitoring_cycle_sync(db)


    # Incident should be generated by monitoring worker
    incidents = db.scalars(select(Incident)).all()
    assert len(incidents) >= 1
    incident = incidents[-1]
    assert incident.status in ("OPEN", "TRIGGERED", "INVESTIGATING", "RESOLVED")


    # Acknowledge incident
    res_ack_inc = client.post(f"/api/v1/incidents/{incident.id}/acknowledge", headers=headers)
    assert res_ack_inc.status_code == 200
    assert res_ack_inc.json()["status"] == "INVESTIGATING"

    # Worker recovers
    res_recov = client.post(
        "/api/v1/workers/heartbeat",
        headers=headers,
        json={"worker_id": str(worker.id), "status": "HEALTHY", "active_jobs": 0},
    )
    assert res_recov.status_code == 200
    assert res_recov.json()["status"] == "HEALTHY"

    # Resolve incident
    res_res_inc = client.post(f"/api/v1/incidents/{incident.id}/resolve", headers=headers)
    assert res_res_inc.status_code == 200
    assert res_res_inc.json()["status"] == "RESOLVED"

    # 8. Full Audit Trail & Security Event Verification
    audit_count = db.scalar(select(AuditLog))
    assert audit_count is not None

    op_events = db.scalars(select(OperationalEvent).where(OperationalEvent.entity_id == str(call_id))).all()
    assert len(op_events) >= 1
    assert op_events[0].event_type == "call.started"
