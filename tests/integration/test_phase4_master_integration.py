from datetime import datetime, timezone
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.ai_infra import AiModel, AiProvider
from app.db.models.organization import Organization
from app.db.models.queue import QueueRegistryItem
from app.db.models.reliability import AlertDefinition
from app.db.models.system_job import SystemJob
from app.db.models.telephony_infra import TelephonyInfrastructure
from app.db.models.user import User
from app.db.models.worker import WorkerNode
from tests.conftest import auth_headers


def test_phase4_full_stack_master_integration(
    client: TestClient,
    db: Session,
    super_admin: User,
    test_org_a: Organization,
):
    """SCENARIO 122: Comprehensive Phase 4 Control Plane & Observability Integration Test.
    
    Verifies all endpoints and full-stack contracts:
    1. System database health endpoint
    2. Worker action dispatcher
    3. Queue action dispatcher
    4. Job retry and cancellation
    5. Alert detail and unified actions
    6. Audit log listing and filtering
    7. Operations live snapshot
    8. API usage and endpoint group health
    9. System logs stream
    10. AI voice infrastructure overview
    11. AI routing rule subpath aliases
    12. Telephony infrastructure nodes
    """
    headers = auth_headers(super_admin)

    # 1. System Database Health
    res_db = client.get("/api/v1/system/database", headers=headers)
    assert res_db.status_code == 200
    db_data = res_db.json()
    assert db_data["connected"] is True
    assert db_data["state"] == "HEALTHY"
    assert "latency" in db_data
    assert "version" in db_data
    assert "migration_status" in db_data

    # 2. Worker Lifecycle & Unified Actions
    worker = WorkerNode(
        scope="PLATFORM",
        worker_type="CAMPAIGN",
        status="HEALTHY",
        hostname="worker-node-integ-01",
        concurrency=8,
        active_jobs=1,
    )
    db.add(worker)
    db.commit()

    res_w_drain = client.post(
        f"/api/v1/workers/{worker.id}/actions",
        headers=headers,
        json={"action": "drain"},
    )
    assert res_w_drain.status_code == 200
    assert res_w_drain.json()["id"] == str(worker.id)

    res_w_resume = client.post(
        f"/api/v1/workers/{worker.id}/actions",
        headers=headers,
        json={"action": "resume"},
    )
    assert res_w_resume.status_code == 200

    # 3. Queue Registry & Unified Actions
    queue = QueueRegistryItem(
        name="integ-test-queue",
        queue_type="DIAL",
        scope="PLATFORM",
        status="HEALTHY",
    )
    db.add(queue)
    db.commit()

    res_q_pause = client.post(
        f"/api/v1/queues/{queue.id}/actions",
        headers=headers,
        json={"action": "pause"},
    )
    assert res_q_pause.status_code == 200
    assert res_q_pause.json()["status"] == "PAUSED"

    res_q_resume = client.post(
        f"/api/v1/queues/{queue.id}/actions",
        headers=headers,
        json={"action": "resume"},
    )
    assert res_q_resume.status_code == 200
    assert res_q_resume.json()["status"] == "HEALTHY"

    # 4. Job Control & Unified Actions
    job = SystemJob(
        scope="PLATFORM",
        queue_id=queue.id,
        worker_id=worker.id,
        job_type="DIAL_DISPATCH",
        status="FAILED",
        attempts=1,
        max_attempts=3,
        scheduled_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()

    res_j_retry = client.post(
        f"/api/v1/jobs/{job.id}/actions",
        headers=headers,
        json={"action": "retry"},
    )
    assert res_j_retry.status_code == 200
    assert res_j_retry.json()["status"] == "QUEUED"

    res_j_cancel = client.post(
        f"/api/v1/jobs/{job.id}/actions",
        headers=headers,
        json={"action": "cancel"},
    )
    assert res_j_cancel.status_code == 200
    assert res_j_cancel.json()["status"] == "CANCELLED"

    # 5. Alert Detail & Unified Actions
    alert = AlertDefinition(
        name="Database Latency Spike Alert",
        metric="db_latency_ms",
        operator="GT",
        threshold=500,
        severity="HIGH",
        scope="PLATFORM",
        state="ACTIVE",
    )
    db.add(alert)
    db.commit()

    res_a_get = client.get(f"/api/v1/alerts/{alert.id}", headers=headers)
    assert res_a_get.status_code == 200
    assert res_a_get.json()["name"] == "Database Latency Spike Alert"

    res_a_ack = client.post(
        f"/api/v1/alerts/{alert.id}/actions",
        headers=headers,
        json={"action": "acknowledge"},
    )
    assert res_a_ack.status_code == 200
    assert res_a_ack.json()["state"] == "ACKNOWLEDGED"

    res_a_res = client.post(
        f"/api/v1/alerts/{alert.id}/actions",
        headers=headers,
        json={"action": "resolve"},
    )
    assert res_a_res.status_code == 200
    assert res_a_res.json()["state"] == "RESOLVED"

    # 6. Audit Log Listing & Filtering
    res_audit = client.get("/api/v1/audit", headers=headers)
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert "items" in audit_data
    assert audit_data["total"] >= 1
    assert any("ALERT" in str(item["action"]) for item in audit_data["items"])

    # 7. Operations Live Snapshot
    res_ops = client.get("/api/v1/operations/snapshot", headers=headers)
    assert res_ops.status_code == 200
    ops_data = res_ops.json()
    assert "workers_total" in ops_data
    assert ops_data["workers_total"] >= 1
    assert "active_calls" in ops_data
    assert "queue_depth" in ops_data

    # 8. API Usage & Endpoint Group Health
    res_usage = client.get("/api/v1/api-usage", headers=headers)
    assert res_usage.status_code == 200
    usage_data = res_usage.json()
    assert usage_data["total_requests"] > 0
    assert len(usage_data["endpoints"]) >= 1

    res_groups = client.get("/api/v1/api-usage/groups", headers=headers)
    assert res_groups.status_code == 200
    groups_data = res_groups.json()
    assert len(groups_data["groups"]) >= 1

    # 9. System Logs Stream
    res_logs = client.get("/api/v1/logs", headers=headers)
    assert res_logs.status_code == 200
    assert "items" in res_logs.json()

    # 10. AI Voice Infrastructure
    res_voice = client.get("/api/v1/ai/voice/infrastructure", headers=headers)
    assert res_voice.status_code == 200
    voice_data = res_voice.json()
    assert "tts_services" in voice_data
    assert len(voice_data["tts_services"]) >= 1

    # 11. AI Routing Rules Subpath Aliases
    prov = AiProvider(
        name="master-integ-ai-prov",
        provider_type="LLM",
        priority=1,
        credential_status="CONFIGURED",
        credential_ref="secret-key-prod-integ",
    )

    db.add(prov)
    db.flush()

    model = AiModel(
        provider_id=prov.id,
        name="claude-3-5-sonnet-20241022",
        model_type="LLM",
    )
    db.add(model)
    db.commit()

    res_rule = client.post(
        "/api/v1/ai/routing/rules",
        headers=headers,
        json={
            "service_type": "LLM",
            "primary_provider_id": str(prov.id),
            "primary_model_id": str(model.id),
            "priority": 1,
            "enabled": True,
        },
    )
    assert res_rule.status_code == 201
    rule_id = res_rule.json()["id"]

    res_rule_patch = client.patch(
        f"/api/v1/ai/routing/rules/{rule_id}",
        headers=headers,
        json={"priority": 2},
    )
    assert res_rule_patch.status_code == 200
    assert res_rule_patch.json()["priority"] == 2

    res_rule_del = client.delete(
        f"/api/v1/ai/routing/rules/{rule_id}",
        headers=headers,
    )
    assert res_rule_del.status_code == 204

    # 12. Telephony Infrastructure Overview
    trunk = TelephonyInfrastructure(
        name="master-sip-carrier",
        type="SIP_TRUNK",
        status="ONLINE",
        capacity=30,
        active_channels=2,
    )
    db.add(trunk)
    db.commit()

    res_tele = client.get("/api/v1/telephony/infrastructure", headers=headers)
    assert res_tele.status_code == 200
    assert len(res_tele.json()) >= 1
