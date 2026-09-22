import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.organization import Organization
from app.db.models.user import User
from tests.conftest import auth_headers


def test_automation_rules_api(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    supervisor_a: User,
):
    headers = auth_headers(supervisor_a)

    # 1. Create Rule
    payload = {
        "name": "Dispute Notification Rule",
        "event_trigger": "dispute_logged",
        "action_type": "send_whatsapp",
        "action_template": "Your dispute has been received and ticket opened.",
        "is_active": True,
        "delay_minutes": 5,
    }
    create_resp = client.post("/api/v1/automation/rules", json=payload, headers=headers)
    assert create_resp.status_code == 201
    rule_data = create_resp.json()["data"]
    rule_id = rule_data["id"]
    assert rule_data["name"] == "Dispute Notification Rule"

    # 2. Update Rule
    update_resp = client.patch(
        f"/api/v1/automation/rules/{rule_id}",
        json={"delay_minutes": 10},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["delay_minutes"] == 10

    # 3. List Rules
    list_resp = client.get("/api/v1/automation/rules", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. List Executions & Jobs
    exec_resp = client.get("/api/v1/automation/executions", headers=headers)
    assert exec_resp.status_code == 200

    jobs_resp = client.get("/api/v1/automation/jobs", headers=headers)
    assert jobs_resp.status_code == 200
