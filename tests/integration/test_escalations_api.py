import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.customer import Customer
from app.db.models.organization import Organization
from app.db.models.user import User
from tests.conftest import auth_headers


def test_escalations_api_workflow(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    supervisor_a: User,
):
    headers = auth_headers(supervisor_a)

    customer = Customer(organization_id=test_org_a.id, name="Grace Hopper")
    db.add(customer)
    db.flush()

    account = Account(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_number=f"ACC-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("18000.00"),
        status="active",
    )
    db.add(account)
    db.commit()

    # 1. Create escalation
    esc_payload = {
        "customer_id": str(customer.id),
        "account_id": str(account.id),
        "reason": "legal_threat",
        "priority": "urgent",
        "resolution_notes": "Customer threatened to contact consumer court",
    }
    create_resp = client.post("/api/v1/escalations", json=esc_payload, headers=headers)
    assert create_resp.status_code == 201
    esc_data = create_resp.json()["data"]
    esc_id = esc_data["id"]
    assert esc_data["status"] == "open"
    assert esc_data["priority"] == "urgent"

    # 2. Update escalation
    update_resp = client.patch(
        f"/api/v1/escalations/{esc_id}",
        json={"status": "resolved", "resolution_notes": "Senior manager resolved issue on call"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["status"] == "resolved"

    # 3. List escalations
    list_resp = client.get("/api/v1/escalations", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1
