import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.customer import Customer
from app.db.models.organization import Organization
from app.db.models.promise_to_pay import PromiseToPay
from app.db.models.user import User
from app.services.recovery.exports import ExportService
from tests.conftest import auth_headers


def test_exports_api_workflow(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    supervisor_a: User,
):
    headers = auth_headers(supervisor_a)

    customer = Customer(organization_id=test_org_a.id, name="Jack Ryan")
    db.add(customer)
    db.flush()

    account = Account(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_number=f"ACC-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("7500.00"),
        status="active",
    )
    db.add(account)
    db.flush()

    ptp = PromiseToPay(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_id=account.id,
        amount=Decimal("3500.00"),
        promised_date=account.created_at,
        status="active",
    )
    db.add(ptp)
    db.commit()

    # 1. Create Export Job (CSV)
    create_resp = client.post(
        "/api/v1/exports",
        json={"export_type": "ptp", "file_format": "csv"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    job_data = create_resp.json()["data"]
    job_id = job_data["id"]

    # Process synchronously in test environment
    ExportService.process_export(db, uuid.UUID(job_id))

    # 2. Check Job Status
    status_resp = client.get(f"/api/v1/exports/{job_id}", headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["data"]["status"] == "completed"

    # 3. Download File
    dl_resp = client.get(f"/api/v1/exports/{job_id}/download", headers=headers)
    assert dl_resp.status_code == 200
    assert b"Amount" in dl_resp.content or b"ID" in dl_resp.content

    # 4. List Exports
    list_resp = client.get("/api/v1/exports", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1
