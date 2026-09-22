import os
from decimal import Decimal

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

XLSX = os.path.join(os.path.dirname(__file__), "..", "fixtures", "valid-recovery.xlsx")
CSV = os.path.join(os.path.dirname(__file__), "..", "fixtures", "valid-recovery.csv")


def _upload(client, headers, path: str):
    with open(path, "rb") as handle:
        return client.post(
            "/api/v1/imports/upload",
            headers=headers,
            files={"file": (os.path.basename(path), handle, "application/octet-stream")},
        )


def test_xlsx_import_matches_csv(client, supervisor_a):
    """The XLSX workflow (the primary one) must behave exactly like CSV."""
    headers = auth_headers(supervisor_a)

    xlsx_upload = _upload(client, headers, XLSX)
    assert xlsx_upload.status_code == 201
    xlsx_data = xlsx_upload.json()["data"]
    assert xlsx_data["file_type"] == "xlsx"
    assert xlsx_data["row_count"] == 3
    assert xlsx_data["detected_columns"] == [
        "Customer Name",
        "Phone Number",
        "Account Number",
        "Outstanding Amount",
        "Due Date",
        "Creditor Name",
        "Email",
    ]

    xlsx_import_id = xlsx_data["import_id"]
    validated = client.post(
        f"/api/v1/imports/{xlsx_import_id}/validate",
        headers=headers,
        json={"mapping": MAPPING},
    )
    assert validated.status_code == 200
    summary = validated.json()["data"]["summary"]
    assert summary == {"total_rows": 3, "valid_rows": 3, "invalid_rows": 0, "duplicate_rows": 0}

    # Values parsed from the spreadsheet are normalized identically to the CSV path.
    preview = validated.json()["data"]["preview"]
    by_account = {row["account_number"]: row for row in preview}
    assert by_account["ACC-1001"]["normalized_phone"] == "+919876543210"
    assert by_account["ACC-1001"]["outstanding_amount"] == "45000.00"
    assert by_account["ACC-1002"]["due_date"] == "2026-11-15"
    assert by_account["ACC-1003"]["normalized_phone"] == "+919123456780"

    confirmed = client.post(f"/api/v1/imports/{xlsx_import_id}/confirm", headers=headers)
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["imported_rows"] == 3
    assert confirmed.json()["data"]["status"] == "completed"

    # Re-confirming is rejected and cannot duplicate records.
    again = client.post(f"/api/v1/imports/{xlsx_import_id}/confirm", headers=headers)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "IMPORT_ALREADY_COMPLETED"

    accounts = client.get("/api/v1/accounts", headers=headers).json()
    assert accounts["total"] == 3
    assert {item["account_number"] for item in accounts["items"]} == {
        "ACC-1001",
        "ACC-1002",
        "ACC-1003",
    }

    amounts = {
        item["account_number"]: Decimal(str(item["outstanding_amount"]))
        for item in accounts["items"]
    }
    assert amounts["ACC-1001"] == Decimal("45000.00")
    assert amounts["ACC-1002"] == Decimal("25000.50")
    assert amounts["ACC-1003"] == Decimal("12500.00")

    customers = client.get("/api/v1/customers", headers=headers).json()
    assert customers["total"] == 3

    creditors = client.get("/api/v1/creditors", headers=headers).json()
    assert {item["name"] for item in creditors["items"]} == {
        "HDFC Bank",
        "SBI Cards",
        "ICICI Bank",
    }


def test_csv_and_xlsx_produce_equivalent_records(client, supervisor_a, org_admin_b):
    """CSV in organization A and XLSX in organization B yield the same shapes."""
    headers_a = auth_headers(supervisor_a)
    headers_b = auth_headers(org_admin_b)

    csv_upload = _upload(client, headers_a, CSV)
    assert csv_upload.status_code == 201
    csv_id = csv_upload.json()["data"]["import_id"]

    xlsx_upload = _upload(client, headers_b, XLSX)
    assert xlsx_upload.status_code == 201
    xlsx_id = xlsx_upload.json()["data"]["import_id"]

    csv_preview = client.post(
        f"/api/v1/imports/{csv_id}/validate", headers=headers_a, json={"mapping": MAPPING}
    ).json()["data"]
    xlsx_preview = client.post(
        f"/api/v1/imports/{xlsx_id}/validate", headers=headers_b, json={"mapping": MAPPING}
    ).json()["data"]

    assert csv_preview["summary"] == xlsx_preview["summary"]
    assert csv_preview["preview"] == xlsx_preview["preview"]

    client.post(f"/api/v1/imports/{csv_id}/confirm", headers=headers_a)
    client.post(f"/api/v1/imports/{xlsx_id}/confirm", headers=headers_b)

    csv_accounts = client.get("/api/v1/accounts", headers=headers_a).json()
    xlsx_accounts = client.get("/api/v1/accounts", headers=headers_b).json()

    def shape(payload):
        return sorted(
            (item["account_number"], item["outstanding_amount"], item["due_date"])
            for item in payload["items"]
        )

    assert shape(csv_accounts) == shape(xlsx_accounts)
