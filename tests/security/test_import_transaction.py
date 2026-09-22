import os

import pytest
from sqlalchemy import select

from app.db.models.account import Account
from app.db.models.creditor import Creditor
from app.db.models.customer import Customer, CustomerPhone
from app.db.models.import_job import Import
from app.services import imports as imports_module
from tests.conftest import auth_headers

MAPPING = {
    "customer_name": "Customer Name",
    "phone": "Phone Number",
    "account_number": "Account Number",
    "outstanding_amount": "Outstanding Amount",
    "due_date": "Due Date",
    "creditor_name": "Creditor Name",
    "email": "Email",
}


def _upload_valid_import(client, headers) -> str:
    fixture_path = os.path.join(
        os.path.dirname(__file__), "..", "fixtures", "valid-recovery.csv"
    )
    with open(fixture_path, "rb") as f:
        response = client.post(
            "/api/v1/imports/upload",
            headers=headers,
            files={"file": ("valid-recovery.csv", f, "text/csv")},
        )
    assert response.status_code == 201
    return response.json()["data"]["import_id"]


def test_confirm_import_rolls_back_on_failure(client, supervisor_a, db, monkeypatch):
    """A failure part-way through confirmation must leave no partial records."""
    headers = auth_headers(supervisor_a)
    import_id = _upload_valid_import(client, headers)

    validated = client.post(
        f"/api/v1/imports/{import_id}/validate", headers=headers, json={"mapping": MAPPING}
    )
    assert validated.status_code == 200
    assert validated.json()["data"]["summary"]["valid_rows"] == 3

    real_account = imports_module.Account
    calls = {"count": 0}

    def exploding_account(**kwargs):
        # Fail while creating the second account, after a customer, phone and
        # creditor from the first row have already been flushed.
        calls["count"] += 1
        if calls["count"] >= 2:
            raise RuntimeError("simulated mid-import database failure")
        return real_account(**kwargs)

    monkeypatch.setattr(imports_module, "Account", exploding_account)

    with pytest.raises(Exception):
        client.post(f"/api/v1/imports/{import_id}/confirm", headers=headers)

    monkeypatch.undo()

    # Nothing from the failed batch may survive.
    assert db.scalars(select(Customer)).all() == []
    assert db.scalars(select(CustomerPhone)).all() == []
    assert db.scalars(select(Account)).all() == []
    assert db.scalars(select(Creditor)).all() == []

    # And the job must not have been marked completed.
    db.expire_all()
    import_job = db.scalar(select(Import).where(Import.id == import_id))
    assert import_job is not None
    assert import_job.status != "completed"
    assert import_job.imported_rows == 0


def test_import_status_persists_across_requests(client, supervisor_a):
    """Import history survives re-reading through a fresh request."""
    headers = auth_headers(supervisor_a)
    import_id = _upload_valid_import(client, headers)

    client.post(f"/api/v1/imports/{import_id}/validate", headers=headers, json={"mapping": MAPPING})
    confirmed = client.post(f"/api/v1/imports/{import_id}/confirm", headers=headers)
    assert confirmed.status_code == 200

    detail = client.get(f"/api/v1/imports/{import_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["status"] == "completed"
    assert body["imported_rows"] == 3
    assert body["total_rows"] == 3

    history = client.get("/api/v1/imports", headers=headers)
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["id"] == import_id
