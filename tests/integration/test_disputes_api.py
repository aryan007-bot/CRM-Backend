import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.customer import Customer
from app.db.models.organization import Organization
from app.db.models.user import User
from tests.conftest import auth_headers


def test_disputes_api_workflow(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    supervisor_a: User,
):
    headers = auth_headers(supervisor_a)

    customer = Customer(organization_id=test_org_a.id, name="Frank Castle")
    db.add(customer)
    db.flush()

    account = Account(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_number=f"ACC-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("20000.00"),
        status="active",
    )
    db.add(account)
    db.commit()

    # 1. Create dispute
    disp_payload = {
        "customer_id": str(customer.id),
        "account_id": str(account.id),
        "reason_category": "fraud",
        "dispute_details": "Customer claims identity theft, never opened this account",
        "evidence_provided": True,
    }
    create_resp = client.post("/api/v1/disputes", json=disp_payload, headers=headers)
    assert create_resp.status_code == 201
    disp_data = create_resp.json()["data"]
    disp_id = disp_data["id"]
    assert disp_data["status"] == "logged"

    # Verify account status is now 'disputed'
    db.refresh(account)
    assert account.status == "disputed"

    # 2. Update dispute: resolve
    update_resp = client.patch(
        f"/api/v1/disputes/{disp_id}",
        json={"status": "resolved", "resolution_notes": "Police report confirmed fraudulent origin"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["status"] == "resolved"

    # 3. List disputes
    list_resp = client.get("/api/v1/disputes", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1
