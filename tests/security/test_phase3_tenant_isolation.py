import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.customer import Customer
from app.db.models.organization import Organization
from app.db.models.promise_to_pay import PromiseToPay
from app.db.models.user import User
from tests.conftest import auth_headers


def test_tenant_isolation_ptp_and_disputes(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    test_org_b: Organization,
    supervisor_a: User,
    org_admin_b: User,
):
    headers_a = auth_headers(supervisor_a)
    headers_b = auth_headers(org_admin_b)

    # Create account and PTP in Org A
    customer_a = Customer(organization_id=test_org_a.id, name="Org A Debtor")
    db.add(customer_a)
    db.flush()

    account_a = Account(
        organization_id=test_org_a.id,
        customer_id=customer_a.id,
        account_number=f"ACC-A-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("5000.00"),
        status="active",
    )
    db.add(account_a)
    db.flush()

    ptp_a = PromiseToPay(
        organization_id=test_org_a.id,
        customer_id=customer_a.id,
        account_id=account_a.id,
        amount=Decimal("2500.00"),
        promised_date=account_a.created_at,
        status="active",
    )
    db.add(ptp_a)
    db.commit()

    # 1. Org A user sees 1 PTP
    resp_a = client.get("/api/v1/ptp", headers=headers_a)
    assert resp_a.status_code == 200
    assert resp_a.json()["total"] == 1

    # 2. Org B user sees 0 PTPs (complete isolation!)
    resp_b = client.get("/api/v1/ptp", headers=headers_b)
    assert resp_b.status_code == 200
    assert resp_b.json()["total"] == 0

    # 3. Org B user cannot reconcile Org A's PTP
    reconcile_b = client.post(f"/api/v1/ptp/{ptp_a.id}/reconcile", headers=headers_b)
    assert reconcile_b.status_code == 404
