import os
from decimal import Decimal

from tests.conftest import auth_headers


def test_complete_phase1_e2e_workflow(client, supervisor_a):
    """Executes the master Phase 1 E2E workflow:
    LOGIN -> UPLOAD -> DETECT -> MAP -> VALIDATE -> CONFIRM -> VERIFY CUSTOMER/ACCOUNT -> CREATE CAMPAIGN -> ADD LEAD -> VERIFY LEAD
    """
    # 1. LOGIN
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "supervisor_a@alpha.com", "password": "Password123!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. UPLOAD valid-recovery.csv
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "valid-recovery.csv")
    with open(fixture_path, "rb") as f:
        upload_resp = client.post(
            "/api/v1/imports/upload",
            headers=headers,
            files={"file": ("valid-recovery.csv", f, "text/csv")},
        )
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()["data"]
    import_id = upload_data["import_id"]
    detected_cols = upload_data["detected_columns"]

    # 3. DETECT COLUMNS
    assert "Customer Name" in detected_cols
    assert "Phone Number" in detected_cols
    assert "Account Number" in detected_cols
    assert "Outstanding Amount" in detected_cols
    assert upload_data["row_count"] == 3

    # 4. MAP COLUMNS
    mapping = {
        "customer_name": "Customer Name",
        "phone": "Phone Number",
        "account_number": "Account Number",
        "outstanding_amount": "Outstanding Amount",
        "due_date": "Due Date",
        "creditor_name": "Creditor Name",
        "email": "Email",
    }

    # 5. VALIDATE
    val_resp = client.post(
        f"/api/v1/imports/{import_id}/validate",
        headers=headers,
        json={"mapping": mapping},
    )
    assert val_resp.status_code == 200
    val_data = val_resp.json()["data"]

    # 6. VERIFY VALID/INVALID/DUPLICATE COUNTS
    summary = val_data["summary"]
    assert summary["total_rows"] == 3
    assert summary["valid_rows"] == 3
    assert summary["invalid_rows"] == 0
    assert summary["duplicate_rows"] == 0
    assert len(val_data["preview"]) == 3

    # 7. CONFIRM IMPORT
    conf_resp = client.post(
        f"/api/v1/imports/{import_id}/confirm",
        headers=headers,
    )
    assert conf_resp.status_code == 200
    assert conf_resp.json()["data"]["imported_rows"] == 3
    assert conf_resp.json()["data"]["status"] == "completed"

    # 8. VERIFY CUSTOMER IN DB
    cust_resp = client.get("/api/v1/customers?search=Rajesh", headers=headers)
    assert cust_resp.status_code == 200
    assert cust_resp.json()["total"] == 1
    customer = cust_resp.json()["items"][0]
    assert customer["name"] == "Rajesh Sharma"
    assert customer["phones"][0]["normalized_phone"] == "+919876543210"

    # 9. VERIFY ACCOUNT IN DB
    acc_resp = client.get("/api/v1/accounts?search=ACC-1001", headers=headers)
    assert acc_resp.status_code == 200
    assert acc_resp.json()["total"] == 1
    account = acc_resp.json()["items"][0]
    account_id = account["id"]
    assert account["account_number"] == "ACC-1001"
    assert Decimal(str(account["outstanding_amount"])) == Decimal("45000.00")
    assert account["customer_name"] == "Rajesh Sharma"
    assert account["creditor_name"] == "HDFC Bank"

    # 10. CREATE CAMPAIGN
    camp_payload = {
        "name": "Phase 1 Recovery Launch Campaign",
        "description": "High priority outreach",
        "timezone": "Asia/Kolkata",
        "calling_start_time": "10:00:00",
        "calling_end_time": "19:00:00",
        "max_attempts": 3,
        "retry_delay_minutes": 120,
        "concurrency_limit": 10,
    }
    camp_resp = client.post("/api/v1/campaigns", headers=headers, json=camp_payload)
    assert camp_resp.status_code == 201
    campaign_id = camp_resp.json()["data"]["id"]

    # 11. ADD ACCOUNT TO CAMPAIGN
    add_lead_resp = client.post(
        f"/api/v1/campaigns/{campaign_id}/leads",
        headers=headers,
        json={"account_ids": [account_id], "priority": 1},
    )
    assert add_lead_resp.status_code == 201
    assert add_lead_resp.json()["data"]["added_leads"] == 1

    # 12. VERIFY CAMPAIGN LEAD
    leads_resp = client.get(f"/api/v1/campaigns/{campaign_id}/leads", headers=headers)
    assert leads_resp.status_code == 200
    leads = leads_resp.json()
    assert leads["total"] == 1
    lead = leads["items"][0]
    assert lead["account_id"] == account_id
    assert lead["account_number"] == "ACC-1001"
    assert lead["customer_name"] == "Rajesh Sharma"
    assert lead["status"] == "pending"


def test_invalid_import_handling(client, supervisor_a):
    headers = auth_headers(supervisor_a)

    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "invalid-recovery.csv")
    with open(fixture_path, "rb") as f:
        up_resp = client.post(
            "/api/v1/imports/upload",
            headers=headers,
            files={"file": ("invalid-recovery.csv", f, "text/csv")},
        )
    assert up_resp.status_code == 201
    import_id = up_resp.json()["data"]["import_id"]

    mapping = {
        "customer_name": "Customer Name",
        "phone": "Phone Number",
        "account_number": "Account Number",
        "outstanding_amount": "Outstanding Amount",
        "due_date": "Due Date",
        "creditor_name": "Creditor Name",
        "email": "Email",
    }

    val_resp = client.post(
        f"/api/v1/imports/{import_id}/validate",
        headers=headers,
        json={"mapping": mapping},
    )
    assert val_resp.status_code == 200
    val_data = val_resp.json()["data"]
    assert val_data["summary"]["invalid_rows"] == 3
    assert val_data["summary"]["valid_rows"] == 0
    assert len(val_data["errors"]) >= 3


def test_duplicate_import_handling(client, supervisor_a):
    headers = auth_headers(supervisor_a)

    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "duplicate-recovery.csv")
    with open(fixture_path, "rb") as f:
        up_resp = client.post(
            "/api/v1/imports/upload",
            headers=headers,
            files={"file": ("duplicate-recovery.csv", f, "text/csv")},
        )
    assert up_resp.status_code == 201
    import_id = up_resp.json()["data"]["import_id"]

    mapping = {
        "customer_name": "Customer Name",
        "phone": "Phone Number",
        "account_number": "Account Number",
        "outstanding_amount": "Outstanding Amount",
        "due_date": "Due Date",
        "creditor_name": "Creditor Name",
        "email": "Email",
    }

    val_resp = client.post(
        f"/api/v1/imports/{import_id}/validate",
        headers=headers,
        json={"mapping": mapping},
    )
    assert val_resp.status_code == 200
    val_data = val_resp.json()["data"]
    # In duplicate-recovery.csv, 1 row is valid, 1 row is duplicate
    assert val_data["summary"]["valid_rows"] == 1
    assert val_data["summary"]["duplicate_rows"] == 1
