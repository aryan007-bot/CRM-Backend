import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.customer import Customer, CustomerPhone
from app.db.models.organization import Organization
from app.db.models.user import User
from tests.conftest import auth_headers


def _setup_test_campaign(db: Session, org: Organization):
    customer = Customer(organization_id=org.id, name="Lead Alpha")
    db.add(customer)
    db.flush()

    phone = CustomerPhone(
        customer_id=customer.id,
        phone="+919999988888",
        normalized_phone="+919999988888",
        is_primary=True,
    )
    db.add(phone)

    account = Account(
        organization_id=org.id,
        customer_id=customer.id,
        account_number=f"ACC-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("15000.00"),
        status="active",
    )
    db.add(account)
    db.flush()

    from datetime import time
    campaign = Campaign(
        organization_id=org.id,
        name="Auto Recovery 1",
        timezone="Asia/Kolkata",
        calling_start_time=time(0, 0),
        calling_end_time=time(23, 59),
        status="draft",
    )
    db.add(campaign)
    db.flush()

    lead = CampaignLead(
        campaign_id=campaign.id,
        account_id=account.id,
        status="pending",
        priority=1,
    )
    db.add(lead)
    db.commit()
    db.refresh(campaign)
    db.refresh(lead)
    return campaign, lead


def test_campaign_validation_and_lifecycle(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    supervisor_a: User,
):
    campaign, lead = _setup_test_campaign(db, test_org_a)
    headers = auth_headers(supervisor_a)

    # 1. Validate
    val_resp = client.post(f"/api/v1/campaigns/{campaign.id}/validate", headers=headers)
    assert val_resp.status_code == 200
    val_data = val_resp.json()["data"]
    assert val_data["valid"] is True
    assert val_data["total_leads"] == 1
    assert val_data["eligible_leads"] == 1

    # 2. Start
    start_resp = client.post(f"/api/v1/campaigns/{campaign.id}/start", headers=headers)
    assert start_resp.status_code == 200
    run_data = start_resp.json()["data"]
    assert run_data["status"] == "active"
    assert run_data["campaign_id"] == str(campaign.id)

    # Verify campaign is running
    camp_resp = client.get(f"/api/v1/campaigns/{campaign.id}", headers=headers)
    assert camp_resp.json()["data"]["status"] == "running"

    # 3. Pause
    pause_resp = client.post(f"/api/v1/campaigns/{campaign.id}/pause", headers=headers)
    assert pause_resp.status_code == 200
    assert pause_resp.json()["data"]["status"] == "paused"

    # 4. Resume
    resume_resp = client.post(f"/api/v1/campaigns/{campaign.id}/resume", headers=headers)
    assert resume_resp.status_code == 200
    assert resume_resp.json()["data"]["status"] == "active"

    # 5. Stop
    stop_resp = client.post(f"/api/v1/campaigns/{campaign.id}/stop", headers=headers)
    assert stop_resp.status_code == 200
    assert stop_resp.json()["data"]["status"] == "completed"

    # 6. Bulk Action on Leads
    bulk_resp = client.post(
        f"/api/v1/campaigns/{campaign.id}/leads/bulk-action",
        json={"lead_ids": [str(lead.id)], "action": "change_priority", "priority": 5},
        headers=headers,
    )
    assert bulk_resp.status_code == 200
    assert bulk_resp.json()["data"]["modified_leads"] == 1
