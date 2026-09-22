import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.customer import Customer
from app.db.models.dial_queue import DialQueueItem
from app.db.models.organization import Organization
from app.db.models.recovery_outcome import RecoveryOutcome
from app.db.models.user import User
from tests.conftest import auth_headers


def test_analytics_api_endpoints(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    supervisor_a: User,
):
    headers = auth_headers(supervisor_a)

    customer = Customer(organization_id=test_org_a.id, name="Iris West")
    db.add(customer)
    db.flush()

    account = Account(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_number=f"ACC-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("10000.00"),
        status="active",
    )
    db.add(account)
    db.flush()

    campaign = Campaign(organization_id=test_org_a.id, name="Analytics Camp")
    db.add(campaign)
    db.flush()

    lead = CampaignLead(
        campaign_id=campaign.id,
        account_id=account.id,
        attempt_count=1,
        contact_state="contacted",
    )
    db.add(lead)
    db.flush()

    queue_item = DialQueueItem(
        organization_id=test_org_a.id,
        campaign_id=campaign.id,
        lead_id=lead.id,
        customer_id=customer.id,
        account_id=account.id,
        phone_number="+919876543210",
        status="completed",
    )
    db.add(queue_item)

    outcome = RecoveryOutcome(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_id=account.id,
        campaign_id=campaign.id,
        outcome_type="ptp",
    )
    db.add(outcome)
    db.commit()

    # 1. Campaign Analytics
    camp_resp = client.get(f"/api/v1/analytics/campaigns/{campaign.id}", headers=headers)
    assert camp_resp.status_code == 200
    camp_data = camp_resp.json()["data"]
    assert camp_data["total_leads"] == 1
    assert camp_data["attempted_leads"] == 1
    assert camp_data["ptp_count"] == 1

    # 2. Org Recovery Metrics
    rec_resp = client.get("/api/v1/analytics/recovery", headers=headers)
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()["data"]
    assert rec_data["total_outcomes"] == 1
    assert rec_data["ptp_count"] == 1

    # 3. Queue Metrics
    queue_resp = client.get("/api/v1/analytics/queue", headers=headers)
    assert queue_resp.status_code == 200
    queue_data = queue_resp.json()["data"]
    assert queue_data["total_queued"] == 1
    assert queue_data["completed_count"] == 1
