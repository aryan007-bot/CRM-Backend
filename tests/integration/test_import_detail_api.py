import os

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


def _upload(client, headers) -> str:
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


def test_import_detail_exposes_columns_and_suggestions(client, supervisor_a):
    """A reloaded mapping screen can rebuild itself from the detail endpoint."""
    headers = auth_headers(supervisor_a)
    import_id = _upload(client, headers)

    detail = client.get(f"/api/v1/imports/{import_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()["data"]

    assert body["detected_columns"] == [
        "Customer Name",
        "Phone Number",
        "Account Number",
        "Outstanding Amount",
        "Due Date",
        "Creditor Name",
        "Email",
    ]
    suggestions = body["suggested_mapping"]
    assert suggestions["customer_name"] == "Customer Name"
    assert suggestions["phone"] == "Phone Number"
    assert suggestions["account_number"] == "Account Number"
    assert suggestions["outstanding_amount"] == "Outstanding Amount"
    assert suggestions["due_date"] == "Due Date"
    assert suggestions["creditor_name"] == "Creditor Name"
    assert suggestions["email"] == "Email"

    # The same data must survive a second read (no request-scoped state).
    again = client.get(f"/api/v1/imports/{import_id}", headers=headers).json()["data"]
    assert again["detected_columns"] == body["detected_columns"]


def test_import_detail_reflects_progress(client, supervisor_a):
    headers = auth_headers(supervisor_a)
    import_id = _upload(client, headers)

    before = client.get(f"/api/v1/imports/{import_id}", headers=headers).json()["data"]
    assert before["status"] == "uploaded"
    assert before["valid_rows"] == 0

    client.post(f"/api/v1/imports/{import_id}/validate", headers=headers, json={"mapping": MAPPING})

    after = client.get(f"/api/v1/imports/{import_id}", headers=headers).json()["data"]
    assert after["status"] == "processing"
    assert after["valid_rows"] == 3
    assert after["invalid_rows"] == 0
    assert after["duplicate_rows"] == 0

    client.post(f"/api/v1/imports/{import_id}/confirm", headers=headers)

    done = client.get(f"/api/v1/imports/{import_id}", headers=headers).json()["data"]
    assert done["status"] == "completed"
    assert done["imported_rows"] == 3

    # The list endpoint keeps the lean summary shape.
    listed = client.get("/api/v1/imports", headers=headers).json()
    assert listed["items"][0]["status"] == "completed"
    assert "detected_columns" not in listed["items"][0]


def test_import_detail_is_tenant_scoped(client, supervisor_a, org_admin_b):
    headers_a = auth_headers(supervisor_a)
    headers_b = auth_headers(org_admin_b)

    import_id = _upload(client, headers_b)
    assert client.get(f"/api/v1/imports/{import_id}", headers=headers_a).status_code == 404
