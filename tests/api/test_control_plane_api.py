import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.ai_infra import AiModel, AiProvider, AiRoutingRule, ProviderQuota
from app.db.models.configuration import ConfigurationItem
from app.db.models.deployment import DeploymentRecord, EnvironmentRecord
from app.db.models.queue import QueueRegistryItem
from app.db.models.reliability import AlertDefinition, Incident
from app.db.models.service import PlatformService
from app.db.models.system_job import SystemJob
from app.db.models.telephony_infra import TelephonyInfrastructure
from app.db.models.user import User
from app.db.models.worker import WorkerNode
from tests.conftest import auth_headers


def test_system_health_and_readiness_api(client: TestClient, super_admin: User):
    headers = auth_headers(super_admin)

    res = client.get("/api/v1/system/health", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "overall_status" in data
    assert "components" in data

    res_ready = client.get("/api/v1/system/readiness", headers=headers)
    assert res_ready.status_code == 200
    assert "ready" in res_ready.json()


def test_services_api(client: TestClient, super_admin: User, db: Session):
    headers = auth_headers(super_admin)

    svc = PlatformService(
        name="api-gateway",
        service_type="API",
        status="HEALTHY",
        scope="PLATFORM",
        environment="production",
    )
    db.add(svc)
    db.commit()

    res = client.get("/api/v1/services", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] >= 1

    res_detail = client.get(f"/api/v1/services/{svc.id}", headers=headers)
    assert res_detail.status_code == 200
    assert res_detail.json()["name"] == "api-gateway"

    res_health = client.get(f"/api/v1/services/{svc.id}/health", headers=headers)
    assert res_health.status_code == 200


def test_workers_and_control_api(client: TestClient, super_admin: User, db: Session):
    headers = auth_headers(super_admin)

    worker = WorkerNode(
        scope="PLATFORM",
        worker_type="CAMPAIGN",
        status="HEALTHY",
        environment="production",
        hostname="worker-test-01",
        concurrency=5,
    )
    db.add(worker)
    db.commit()

    # List
    res = client.get("/api/v1/workers", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] >= 1

    # Heartbeat
    hb_res = client.post(
        "/api/v1/workers/heartbeat",
        headers=headers,
        json={"worker_id": str(worker.id), "status": "HEALTHY", "active_jobs": 1},
    )
    assert hb_res.status_code == 200
    assert hb_res.json()["active_jobs"] == 1

    # Drain
    drain_res = client.post(f"/api/v1/workers/{worker.id}/drain", headers=headers)
    assert drain_res.status_code == 200
    assert drain_res.json()["command"] == "DRAIN"

    # Resume
    resume_res = client.post(f"/api/v1/workers/{worker.id}/resume", headers=headers)
    assert resume_res.status_code == 200
    assert resume_res.json()["command"] == "RESUME"

    # Restart
    restart_res = client.post(f"/api/v1/workers/{worker.id}/restart", headers=headers)
    assert restart_res.status_code == 200
    assert restart_res.json()["command"] == "RESTART"

    # Disable
    disable_res = client.post(f"/api/v1/workers/{worker.id}/disable", headers=headers)
    assert disable_res.status_code == 200
    assert disable_res.json()["command"] == "DISABLE"


def test_queues_and_control_api(client: TestClient, super_admin: User, db: Session):
    headers = auth_headers(super_admin)

    queue = QueueRegistryItem(
        name="test-queue",
        queue_type="DIAL",
        scope="PLATFORM",
        status="HEALTHY",
    )
    db.add(queue)
    db.commit()

    res = client.get("/api/v1/queues", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] >= 1

    # Pause
    res_pause = client.post(f"/api/v1/queues/{queue.id}/pause", headers=headers)
    assert res_pause.status_code == 200
    assert res_pause.json()["status"] == "PAUSED"

    # Resume
    res_resume = client.post(f"/api/v1/queues/{queue.id}/resume", headers=headers)
    assert res_resume.status_code == 200
    assert res_resume.json()["status"] == "HEALTHY"


def test_jobs_and_retry_api(client: TestClient, super_admin: User, db: Session):
    headers = auth_headers(super_admin)

    job = SystemJob(
        scope="PLATFORM",
        job_type="CAMPAIGN_RUN",
        status="FAILED",
        attempts=1,
        max_attempts=3,
    )
    db.add(job)
    db.commit()

    res = client.get("/api/v1/jobs", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] >= 1

    res_detail = client.get(f"/api/v1/jobs/{job.id}", headers=headers)
    assert res_detail.status_code == 200
    assert res_detail.json()["status"] == "FAILED"

    # Retry
    res_retry = client.post(f"/api/v1/jobs/{job.id}/retry", headers=headers)
    assert res_retry.status_code == 200
    assert res_retry.json()["status"] == "QUEUED"
    assert res_retry.json()["attempts"] == 2

    # Running job rejection test
    job.status = "RUNNING"
    db.commit()
    res_running_retry = client.post(f"/api/v1/jobs/{job.id}/retry", headers=headers)
    assert res_running_retry.status_code == 400
    assert res_running_retry.json()["error"]["code"] == "JOB_NOT_RETRYABLE"


def test_telephony_infrastructure_api(client: TestClient, super_admin: User, db: Session):
    headers = auth_headers(super_admin)

    node = TelephonyInfrastructure(
        scope="PLATFORM",
        type="ASTERISK",
        name="asterisk-node-01",
        status="ONLINE",
        capacity=60,
    )
    db.add(node)
    db.commit()

    res = client.get("/api/v1/telephony/infrastructure", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1

    res_node = client.get(f"/api/v1/telephony/infrastructure/{node.id}", headers=headers)
    assert res_node.status_code == 200
    assert res_node.json()["name"] == "asterisk-node-01"


def test_ai_infrastructure_providers_models_routing_api(client: TestClient, super_admin: User, db: Session):
    headers = auth_headers(super_admin)

    # 1. AI Infrastructure overview
    res_infra = client.get("/api/v1/ai/infrastructure", headers=headers)
    assert res_infra.status_code == 200

    # 2. Create Provider
    res_prov = client.post(
        "/api/v1/ai/providers",
        headers=headers,
        json={
            "name": "groq-fast",
            "provider_type": "LLM",
            "priority": 1,
            "api_key": "gsk_test_12345678",
        },
    )
    assert res_prov.status_code == 201
    prov_data = res_prov.json()
    assert prov_data["name"] == "groq-fast"
    assert prov_data["credential_status"] == "CONFIGURED"
    assert "api_key" not in prov_data  # Never return plaintext secret
    prov_id = prov_data["id"]

    # 3. Health check provider
    res_hc = client.post(f"/api/v1/ai/providers/{prov_id}/health-check", headers=headers)
    assert res_hc.status_code == 200
    assert res_hc.json()["status"] == "HEALTHY"

    # 4. Create Model
    res_model = client.post(
        "/api/v1/ai/models",
        headers=headers,
        json={
            "provider_id": prov_id,
            "name": "llama-3.3-70b-versatile",
            "model_type": "LLM",
        },
    )
    assert res_model.status_code == 201
    model_id = res_model.json()["id"]

    # 5. Create Routing Rule
    res_rule = client.post(
        "/api/v1/ai/routing",
        headers=headers,
        json={
            "service_type": "LLM",
            "primary_provider_id": prov_id,
            "primary_model_id": model_id,
            "priority": 1,
        },
    )
    assert res_rule.status_code == 201
    rule_id = res_rule.json()["id"]

    # 6. Usage and latency
    res_usage = client.get("/api/v1/ai/usage", headers=headers)
    assert res_usage.status_code == 200

    res_latency = client.get("/api/v1/ai/latency?service_type=LLM", headers=headers)
    assert res_latency.status_code == 200

    res_quota = client.get("/api/v1/ai/quota", headers=headers)
    assert res_quota.status_code == 200


def test_capacity_and_performance_api(client: TestClient, super_admin: User):
    headers = auth_headers(super_admin)

    res_cap = client.get("/api/v1/capacity", headers=headers)
    assert res_cap.status_code == 200
    assert "active_calls" in res_cap.json()
    assert "worker_capacity" in res_cap.json()

    res_perf = client.get("/api/v1/performance", headers=headers)
    assert res_perf.status_code == 200
    assert "api_p50_latency_ms" in res_perf.json()


def test_incidents_and_alerts_api(client: TestClient, super_admin: User, db: Session):
    headers = auth_headers(super_admin)

    # Create Alert
    res_al = client.post(
        "/api/v1/alerts",
        headers=headers,
        json={
            "name": "high-stt-latency",
            "metric": "stt_latency_ms",
            "operator": "GT",
            "threshold": 500,
            "severity": "HIGH",
        },
    )
    assert res_al.status_code == 201
    alert_id = res_al.json()["id"]

    # List alerts
    res_list = client.get("/api/v1/alerts", headers=headers)
    assert res_list.status_code == 200

    # Acknowledge Alert
    res_ack_al = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=headers)
    assert res_ack_al.status_code == 200
    assert res_ack_al.json()["state"] == "ACKNOWLEDGED"

    # Create Incident
    inc = Incident(
        scope="PLATFORM",
        title="STT Cluster Degraded",
        description="High packet loss",
        severity="HIGH",
        status="OPEN",
    )
    db.add(inc)
    db.commit()

    # List incidents
    res_inc = client.get("/api/v1/incidents", headers=headers)
    assert res_inc.status_code == 200
    assert res_inc.json()["total"] >= 1

    # Acknowledge incident
    res_ack = client.post(f"/api/v1/incidents/{inc.id}/acknowledge", headers=headers)
    assert res_ack.status_code == 200
    assert res_ack.json()["status"] == "INVESTIGATING"

    # Resolve incident
    res_res = client.post(f"/api/v1/incidents/{inc.id}/resolve", headers=headers)
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "RESOLVED"


def test_deployments_and_environments_api(client: TestClient, super_admin: User, db: Session):
    headers = auth_headers(super_admin)

    # Environments
    res_env = client.get("/api/v1/environments", headers=headers)
    assert res_env.status_code == 200
    envs = res_env.json()
    assert len(envs) >= 1
    env_id = envs[0]["id"]

    # Trigger deployment
    res_dep = client.post(
        "/api/v1/deployments",
        headers=headers,
        json={
            "environment_id": env_id,
            "version": "1.1.0",
            "commit_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        },
    )
    assert res_dep.status_code == 201
    dep_id = res_dep.json()["id"]

    # Rollback deployment
    res_rb = client.post(f"/api/v1/deployments/{dep_id}/rollback", headers=headers, json={"target_version": "1.0.0"})
    assert res_rb.status_code == 200
    assert res_rb.json()["status"] == "ROLLED_BACK"


def test_configuration_api(client: TestClient, super_admin: User, db: Session):
    headers = auth_headers(super_admin)

    res_cfg = client.get("/api/v1/configuration", headers=headers)
    assert res_cfg.status_code == 200
    items = res_cfg.json()
    assert len(items) >= 1

    item_id = items[0]["id"]
    res_item = client.get(f"/api/v1/configuration/{item_id}", headers=headers)
    assert res_item.status_code == 200

    # History
    res_hist = client.get(f"/api/v1/configuration/{item_id}/history", headers=headers)
    assert res_hist.status_code == 200


def test_events_and_security_events_api(client: TestClient, super_admin: User):
    headers = auth_headers(super_admin)

    res_ev = client.get("/api/v1/events", headers=headers)
    assert res_ev.status_code == 200

    res_sec = client.get("/api/v1/security/events", headers=headers)
    assert res_sec.status_code == 200
