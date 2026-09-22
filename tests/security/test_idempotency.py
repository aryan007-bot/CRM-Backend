import os

from tests.conftest import auth_headers


def test_import_confirmation_idempotency(client, supervisor_a):
    headers = auth_headers(supervisor_a)

    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "valid-recovery.csv")
    with open(fixture_path, "rb") as f:
        up_resp = client.post(
            "/api/v1/imports/upload",
            headers=headers,
            files={"file": ("valid.csv", f, "text/csv")},
        )
    assert up_resp.status_code == 201
    imp_id = up_resp.json()["data"]["import_id"]

    # Validate mapping
    mapping = {
        "customer_name": "Customer Name",
        "phone": "Phone Number",
        "account_number": "Account Number",
        "outstanding_amount": "Outstanding Amount",
        "due_date": "Due Date",
        "creditor_name": "Creditor Name",
        "email": "Email",
    }
    val_resp = client.post(f"/api/v1/imports/{imp_id}/validate", headers=headers, json={"mapping": mapping})
    assert val_resp.status_code == 200
    assert val_resp.json()["data"]["summary"]["valid_rows"] == 3

    # Confirm import (1st time) -> 200
    conf_resp1 = client.post(f"/api/v1/imports/{imp_id}/confirm", headers=headers)
    assert conf_resp1.status_code == 200
    assert conf_resp1.json()["data"]["imported_rows"] == 3

    # Check initial account count
    acc_list1 = client.get("/api/v1/accounts", headers=headers)
    assert acc_list1.json()["total"] == 3

    # Confirm import (2nd time) -> 409 Conflict
    conf_resp2 = client.post(f"/api/v1/imports/{imp_id}/confirm", headers=headers)
    assert conf_resp2.status_code == 409
    assert conf_resp2.json()["error"]["code"] == "IMPORT_ALREADY_COMPLETED"

    # Verify no records were duplicated
    acc_list2 = client.get("/api/v1/accounts", headers=headers)
    assert acc_list2.json()["total"] == 3
