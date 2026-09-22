from decimal import Decimal

from tests.conftest import auth_headers


def test_accounts_and_payments_workflow(client, supervisor_a):
    headers = auth_headers(supervisor_a)

    # 1. Create Creditor
    cred_resp = client.post(
        "/api/v1/creditors",
        headers=headers,
        json={"name": "HDFC Bank", "status": "active"},
    )
    assert cred_resp.status_code == 201
    cred_id = cred_resp.json()["data"]["id"]

    # 2. Create Customer
    cust_resp = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Suresh Gupta", "phones": [{"phone": "9811223344", "is_primary": True}]},
    )
    assert cust_resp.status_code == 201
    cust_id = cust_resp.json()["data"]["id"]

    # 3. Create Account
    acc_payload = {
        "customer_id": cust_id,
        "creditor_id": cred_id,
        "account_number": "ACC-HDFC-999",
        "outstanding_amount": 50000.00,
        "due_date": "2026-12-31",
        "status": "active",
    }
    acc_resp = client.post("/api/v1/accounts", headers=headers, json=acc_payload)
    assert acc_resp.status_code == 201
    acc_data = acc_resp.json()["data"]
    acc_id = acc_data["id"]
    assert acc_data["account_number"] == "ACC-HDFC-999"
    assert Decimal(str(acc_data["outstanding_amount"])) == Decimal("50000.00")
    assert acc_data["customer_name"] == "Suresh Gupta"
    assert acc_data["creditor_name"] == "HDFC Bank"

    # 4. Duplicate Account Number Rejection
    dup_resp = client.post("/api/v1/accounts", headers=headers, json=acc_payload)
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"]["code"] == "ACCOUNT_EXISTS"

    # 5. Add Payment
    pay_resp = client.post(
        f"/api/v1/accounts/{acc_id}/payments",
        headers=headers,
        json={
            "amount": 20000.00,
            "currency": "INR",
            "reference": "UPI-REF-12345",
            "notes": "Partial settlement payment",
        },
    )
    assert pay_resp.status_code == 201
    assert Decimal(str(pay_resp.json()["data"]["amount"])) == Decimal("20000.00")

    # 6. Verify Account Balance Updated
    get_acc = client.get(f"/api/v1/accounts/{acc_id}", headers=headers)
    assert get_acc.status_code == 200
    updated_acc = get_acc.json()["data"]
    assert Decimal(str(updated_acc["outstanding_amount"])) == Decimal("30000.00")
    assert len(updated_acc["payments"]) == 1
