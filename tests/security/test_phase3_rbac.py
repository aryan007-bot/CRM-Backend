import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.campaign import Campaign
from app.db.models.organization import Organization
from app.db.models.user import User
from tests.conftest import auth_headers


def test_viewer_role_cannot_mutate_campaigns_or_rules(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    viewer_a: User,
):
    headers = auth_headers(viewer_a)

    campaign = Campaign(organization_id=test_org_a.id, name="RBAC Camp")
    db.add(campaign)
    db.commit()

    # 1. Start campaign forbidden for VIEWER
    start_resp = client.post(f"/api/v1/campaigns/{campaign.id}/start", headers=headers)
    assert start_resp.status_code == 403

    # 2. Reserve queue forbidden for VIEWER
    reserve_resp = client.post(
        "/api/v1/recovery/queue/reserve",
        json={"worker_id": "bad-actor", "batch_size": 1},
        headers=headers,
    )
    assert reserve_resp.status_code == 403

    # 3. Create automation rule forbidden for VIEWER
    rule_resp = client.post(
        "/api/v1/automation/rules",
        json={"name": "Test", "event_trigger": "ptp_created", "action_type": "send_sms"},
        headers=headers,
    )
    assert rule_resp.status_code == 403
