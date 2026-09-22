import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.account import Account, AccountPayment
from app.db.models.customer import Customer
from app.db.models.organization import Organization
from app.db.models.user import User
from tests.conftest import auth_headers


def test_ptp_api_workflow(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    supervisor_a: User,
):
    headers = auth_headers(supervisor_a)

    customer = Customer(organization_id=test_org_a.id, name="David Warner")
    db.add(customer)
    db.flush()

    account = Account(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_number=f"ACC-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("8000.00"),
        status="active",
    )
    db.add(account)
    db.commit()

    # 1. Create PTP
    ptp_payload = {
        "customer_id": str(customer.id),
        "account_id": str(account.id),
        "amount": "4000.00",
        "promised_date": "2026-10-15T09:00:00Z",
        "grace_period_days": 2,
        "notes": "Promised payment next payday",
    }
    create_resp = client.post("/api/v1/ptp", json=ptp_payload, headers=headers)
    assert create_resp.status_code == 201
    ptp_data = create_resp.json()["data"]
    ptp_id = ptp_data["id"]
    assert ptp_data["status"] == "active"
    assert Decimal(ptp_data["amount"]) == Decimal("4000.00")

    # 2. Update PTP
    update_resp = client.patch(
        f"/api/v1/ptp/{ptp_id}",
        json={"notes": "Updated note: confirmed via SMS"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["notes"] == "Updated note: confirmed via SMS"

    # 3. Add payment and reconcile
    payment = AccountPayment(
        account_id=account.id,
        amount=Decimal("4000.00"),
        payment_date=account.created_at,
        reference="TXN-9988",
    )
    db.add(payment)
    db.commit()

    reconcile_resp = client.post(f"/api/v1/ptp/{ptp_id}/reconcile", headers=headers)
    assert reconcile_resp.status_code == 200
    rec_data = reconcile_resp.json()["data"]
    assert rec_data["current_status"] == "kept"
    assert Decimal(str(rec_data["total_paid"])) == Decimal("4000.00")

    # 4. List PTP
    list_resp = client.get("/api/v1/ptp", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1
