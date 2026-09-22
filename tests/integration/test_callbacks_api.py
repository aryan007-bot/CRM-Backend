import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.customer import Customer
from app.db.models.organization import Organization
from app.db.models.user import User
from tests.conftest import auth_headers


def test_callbacks_api_workflow(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    supervisor_a: User,
):
    headers = auth_headers(supervisor_a)

    customer = Customer(organization_id=test_org_a.id, name="Emma Watson")
    db.add(customer)
    db.flush()

    account = Account(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_number=f"ACC-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("3000.00"),
        status="active",
    )
    db.add(account)
    db.commit()

    # 1. Create callback
    cb_payload = {
        "customer_id": str(customer.id),
        "account_id": str(account.id),
        "scheduled_time": "2026-09-25T14:30:00Z",
        "phone_number": "+919876543210",
        "requested_by": "customer",
        "notes": "Customer requested callback after lunch",
    }
    create_resp = client.post("/api/v1/callbacks", json=cb_payload, headers=headers)
    assert create_resp.status_code == 201
    cb_data = create_resp.json()["data"]
    cb_id = cb_data["id"]
    assert cb_data["status"] == "pending"

    # 2. Update callback
    update_resp = client.patch(
        f"/api/v1/callbacks/{cb_id}",
        json={"status": "completed"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["status"] == "completed"

    # 3. List callbacks
    list_resp = client.get("/api/v1/callbacks", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1
