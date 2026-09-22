from decimal import Decimal

from tests.conftest import auth_headers


def test_dashboard_summary_empty(client, supervisor_a):
    headers = auth_headers(supervisor_a)
    response = client.get("/api/v1/dashboard/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]

    # Must be real zero counts
    assert data["customers"] == 0
    assert data["accounts"] == 0
    assert Decimal(str(data["total_outstanding"])) == Decimal("0.00")
    assert data["active_campaigns"] == 0
    assert data["pending_imports"] == 0


def test_dashboard_summary_with_records(client, supervisor_a):
    headers = auth_headers(supervisor_a)

    # Create a customer
    c_resp = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Dashboard Tester", "phones": [{"phone": "9876543210", "is_primary": True}]},
    )
    assert c_resp.status_code == 201
    cust_id = c_resp.json()["data"]["id"]

    # Create an account
    a_resp = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "customer_id": cust_id,
            "account_number": "DASH-001",
            "outstanding_amount": 5500.50,
            "status": "active",
        },
    )
    assert a_resp.status_code == 201

    # Verify dashboard reflects the counts
    d_resp = client.get("/api/v1/dashboard/summary", headers=headers)
    assert d_resp.status_code == 200
    data = d_resp.json()["data"]
    assert data["customers"] == 1
    assert data["accounts"] == 1
    assert Decimal(str(data["total_outstanding"])) == Decimal("5500.50")
