import uuid

import pytest

from tests.conftest import auth_headers


def test_invalid_email_format(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "Password123!"},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_not_found_customer_and_account(client, supervisor_a):
    headers = auth_headers(supervisor_a)
    random_id = uuid.uuid4()

    c_resp = client.get(f"/api/v1/customers/{random_id}", headers=headers)
    assert c_resp.status_code == 404
    assert c_resp.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"

    a_resp = client.get(f"/api/v1/accounts/{random_id}", headers=headers)
    assert a_resp.status_code == 404
    assert a_resp.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


def test_invalid_uuid_param(client, supervisor_a):
    headers = auth_headers(supervisor_a)
    resp = client.get("/api/v1/customers/not-a-valid-uuid", headers=headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_oversized_upload_rejection(client, supervisor_a, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 50)  # artificially low limit for test

    headers = auth_headers(supervisor_a)
    large_content = b"x" * 100
    resp = client.post(
        "/api/v1/imports/upload",
        headers=headers,
        files={"file": ("test.csv", large_content, "text/csv")},
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_missing_required_mapping_rejection(client, supervisor_a):
    headers = auth_headers(supervisor_a)

    # Upload valid file
    content = b"Name,Phone,Account,Amount\nJohn,9876543210,A1,1000\n"
    up_resp = client.post(
        "/api/v1/imports/upload",
        headers=headers,
        files={"file": ("test.csv", content, "text/csv")},
    )
    import_id = up_resp.json()["data"]["import_id"]

    # Provide incomplete mapping (missing outstanding_amount)
    incomplete_map = {
        "customer_name": "Name",
        "phone": "Phone",
        "account_number": "Account",
    }
    val_resp = client.post(
        f"/api/v1/imports/{import_id}/validate",
        headers=headers,
        json={"mapping": incomplete_map},
    )
    assert val_resp.status_code == 400
    assert "Missing required field mappings" in val_resp.json()["error"]["message"]
