import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.customer import Customer, CustomerPhone
from app.db.models.dial_queue import DialQueueItem
from app.db.models.organization import Organization
from app.db.models.user import User
from tests.conftest import auth_headers


def test_dial_queue_endpoints(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    supervisor_a: User,
):
    headers = auth_headers(supervisor_a)

    customer = Customer(organization_id=test_org_a.id, name="Queue Lead")
    db.add(customer)
    db.flush()

    phone = CustomerPhone(customer_id=customer.id, phone="+919876543210", normalized_phone="+919876543210")
    db.add(phone)

    account = Account(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_number=f"ACC-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("5000.00"),
        status="active",
    )
    db.add(account)
    db.flush()

    campaign = Campaign(organization_id=test_org_a.id, name="Dial Campaign")
    db.add(campaign)
    db.flush()

    lead = CampaignLead(campaign_id=campaign.id, account_id=account.id, priority=2)
    db.add(lead)
    db.flush()

    item = DialQueueItem(
        organization_id=test_org_a.id,
        campaign_id=campaign.id,
        lead_id=lead.id,
        customer_id=customer.id,
        account_id=account.id,
        phone_number="+919876543210",
        priority=2,
        status="pending",
    )
    db.add(item)
    db.commit()

    # 1. List Queue
    list_resp = client.get("/api/v1/recovery/queue", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 2. Reserve Batch
    reserve_resp = client.post(
        "/api/v1/recovery/queue/reserve",
        json={"worker_id": "worker-1", "batch_size": 1},
        headers=headers,
    )
    assert reserve_resp.status_code == 200
    res_data = reserve_resp.json()["data"]
    assert res_data["reserved_count"] == 1
    reserved_item = res_data["items"][0]
    assert reserved_item["status"] == "reserved"

    # 3. Release Reservation
    rel_resp = client.post(
        f"/api/v1/recovery/queue/{item.id}/release",
        headers=headers,
    )
    assert rel_resp.status_code == 200
    assert rel_resp.json()["data"]["status"] == "pending"

    # 4. Complete Item
    comp_resp = client.post(
        f"/api/v1/recovery/queue/{item.id}/complete?completion_status=completed",
        headers=headers,
    )
    assert comp_resp.status_code == 200
    assert comp_resp.json()["data"]["status"] == "completed"
