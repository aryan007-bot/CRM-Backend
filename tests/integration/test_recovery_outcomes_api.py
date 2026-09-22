import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.customer import Customer
from app.db.models.organization import Organization
from app.db.models.user import User
from tests.conftest import auth_headers


def test_recovery_outcomes_lifecycle(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    supervisor_a: User,
):
    headers = auth_headers(supervisor_a)

    customer = Customer(organization_id=test_org_a.id, name="Charlie Brown")
    db.add(customer)
    db.flush()

    account = Account(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_number=f"ACC-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("12000.00"),
        status="active",
    )
    db.add(account)
    db.commit()

    # 1. Record outcome: PTP
    outcome_payload = {
        "customer_id": str(customer.id),
        "account_id": str(account.id),
        "outcome_type": "ptp",
        "details": {"amount": "6000.00", "promised_date": "2026-10-01T10:00:00Z"},
        "notes": "Customer promised partial payment by 1st of next month",
        "recorded_by": "ai",
    }
    rec_resp = client.post("/api/v1/recovery/outcomes", json=outcome_payload, headers=headers)
    assert rec_resp.status_code == 201
    outcome_data = rec_resp.json()["data"]
    assert outcome_data["outcome_type"] == "ptp"

    # 2. List outcomes
    list_resp = client.get("/api/v1/recovery/outcomes", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 3. Get Summary
    summary_resp = client.get("/api/v1/recovery/summary", headers=headers)
    assert summary_resp.status_code == 200
    summary_data = summary_resp.json()["data"]
    assert summary_data["total_calls"] == 1
    assert summary_data["ptp_count"] == 1
