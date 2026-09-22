import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.customer import Customer
from app.db.models.dial_queue import DialQueueItem
from app.db.models.organization import Organization
from app.db.models.user import User
from tests.conftest import auth_headers


def test_concurrent_queue_reservation_no_duplicates(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    supervisor_a: User,
):
    headers = auth_headers(supervisor_a)

    # Setup 10 queue items
    customer = Customer(organization_id=test_org_a.id, name="Concurrent Customer")
    db.add(customer)
    db.flush()

    account = Account(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_number=f"ACC-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("1000.00"),
        status="active",
    )
    db.add(account)
    db.flush()

    campaign = Campaign(organization_id=test_org_a.id, name="Concurrency Camp")
    db.add(campaign)
    db.flush()

    lead = CampaignLead(campaign_id=campaign.id, account_id=account.id)
    db.add(lead)
    db.flush()

    items = []
    for i in range(10):
        item = DialQueueItem(
            organization_id=test_org_a.id,
            campaign_id=campaign.id,
            lead_id=lead.id,
            customer_id=customer.id,
            account_id=account.id,
            phone_number=f"+91987654321{i}",
            priority=1,
            status="pending",
        )
        items.append(item)
    db.add_all(items)
    db.commit()

    reserved_item_ids = []

    # Simulate multi-worker reservations
    for i in range(5):
        resp = client.post(
            "/api/v1/recovery/queue/reserve",
            json={"worker_id": f"worker-{i}", "batch_size": 2},
            headers=headers,
        )
        assert resp.status_code == 200
        batch = resp.json()["data"]["items"]
        assert len(batch) == 2
        for b in batch:
            reserved_item_ids.append(b["id"])

    # Every reserved item must be unique! No duplicate reservations!
    assert len(reserved_item_ids) == len(set(reserved_item_ids))
    assert len(reserved_item_ids) == 10

    # Next reservation returns 0 items because queue is fully reserved
    resp_empty = client.post(
        "/api/v1/recovery/queue/reserve",
        json={"worker_id": "worker-extra", "batch_size": 2},
        headers=headers,
    )
    assert resp_empty.status_code == 200
    assert resp_empty.json()["data"]["reserved_count"] == 0
