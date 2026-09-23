import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.ai_infra import AiProvider
from app.db.models.configuration import ConfigurationItem
from app.db.models.reliability import AlertDefinition, Incident
from app.db.models.system_job import SystemJob
from app.db.models.user import User
from tests.conftest import auth_headers


def test_tenant_isolation_ai_providers(client: TestClient, org_admin_a: User, org_admin_b: User, db: Session):
    headers_a = auth_headers(org_admin_a)
    headers_b = auth_headers(org_admin_b)

    # Provider owned by Org A
    prov_a = AiProvider(
        name="custom-org-a-llm",
        provider_type="LLM",
        scope="ORGANIZATION",
        organization_id=org_admin_a.organization_id,
        priority=1,
        enabled=True,
    )
    # Provider owned by Org B
    prov_b = AiProvider(
        name="custom-org-b-llm",
        provider_type="LLM",
        scope="ORGANIZATION",
        organization_id=org_admin_b.organization_id,
        priority=1,
        enabled=True,
    )
    db.add_all([prov_a, prov_b])
    db.commit()

    # Org A lists providers -> only sees prov_a (and global platform providers)
    res_a = client.get("/api/v1/ai/providers", headers=headers_a)
    assert res_a.status_code == 200
    names_a = [p["name"] for p in res_a.json()["items"]]
    assert "custom-org-a-llm" in names_a
    assert "custom-org-b-llm" not in names_a

    # Org B lists providers -> only sees prov_b
    res_b = client.get("/api/v1/ai/providers", headers=headers_b)
    assert res_b.status_code == 200
    names_b = [p["name"] for p in res_b.json()["items"]]
    assert "custom-org-b-llm" in names_b
    assert "custom-org-a-llm" not in names_b


def test_tenant_isolation_incidents_and_jobs(client: TestClient, org_admin_a: User, org_admin_b: User, db: Session):
    headers_a = auth_headers(org_admin_a)
    headers_b = auth_headers(org_admin_b)

    # Incidents
    inc_a = Incident(
        scope="ORGANIZATION",
        organization_id=org_admin_a.organization_id,
        title="Org A Incident",
        description="Org A specific issue",
        severity="MEDIUM",
    )
    inc_b = Incident(
        scope="ORGANIZATION",
        organization_id=org_admin_b.organization_id,
        title="Org B Incident",
        description="Org B specific issue",
        severity="MEDIUM",
    )
    db.add_all([inc_a, inc_b])

    # Jobs
    job_a = SystemJob(
        scope="ORGANIZATION",
        organization_id=org_admin_a.organization_id,
        job_type="EXPORT",
        status="QUEUED",
    )
    job_b = SystemJob(
        scope="ORGANIZATION",
        organization_id=org_admin_b.organization_id,
        job_type="EXPORT",
        status="QUEUED",
    )
    db.add_all([job_a, job_b])
    db.commit()

    # Check incidents
    res_inc_a = client.get("/api/v1/incidents", headers=headers_a)
    assert res_inc_a.status_code == 200
    titles_a = [i["title"] for i in res_inc_a.json()["items"]]
    assert "Org A Incident" in titles_a
    assert "Org B Incident" not in titles_a

    # Check jobs
    res_job_a = client.get("/api/v1/jobs", headers=headers_a)
    assert res_job_a.status_code == 200
    job_ids_a = [j["id"] for j in res_job_a.json()["items"]]
    assert str(job_a.id) in job_ids_a
    assert str(job_b.id) not in job_ids_a


def test_rbac_viewer_cannot_execute_privileged_operations(client: TestClient, viewer_a: User, db: Session):
    headers_viewer = auth_headers(viewer_a)

    # Viewer cannot restart worker
    fake_worker_id = uuid.uuid4()
    res_drain = client.post(f"/api/v1/workers/{fake_worker_id}/drain", headers=headers_viewer)
    assert res_drain.status_code in (401, 403)

    # Viewer cannot rollback deployment
    fake_dep_id = uuid.uuid4()
    res_rb = client.post(f"/api/v1/deployments/{fake_dep_id}/rollback", headers=headers_viewer)
    assert res_rb.status_code in (401, 403)

    # Viewer cannot update configuration
    fake_cfg_id = uuid.uuid4()
    res_cfg = client.patch(f"/api/v1/configuration/{fake_cfg_id}", headers=headers_viewer, json={"value": 10})
    assert res_cfg.status_code in (401, 403)


def test_no_secret_leaks_in_configuration(client: TestClient, super_admin: User, db: Session):
    headers = auth_headers(super_admin)

    cfg = ConfigurationItem(
        scope="PLATFORM",
        key="test.db.password",
        value_type="string",
        is_secret=True,
        is_mutable=True,
        safe_value="******",
        secret_ref="vault://secret/db/password",
        state="APPLIED",
    )
    db.add(cfg)
    db.commit()

    res = client.get(f"/api/v1/configuration/{cfg.id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["safe_value"] == "******"
    assert "vault://" not in str(data)
