import uuid

from tests.conftest import auth_headers


def test_customers_crud_workflow(client, supervisor_a, org_admin_a):
    headers = auth_headers(supervisor_a)

    # 1. List initially empty
    resp = client.get("/api/v1/customers", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["items"] == []

    # 2. Create customer
    create_payload = {
        "name": "Aarav Patel",
        "email": "aarav@example.com",
        "status": "active",
        "phones": [
            {"phone": "+91 98765 43210", "phone_type": "mobile", "is_primary": True}
        ],
    }
    c_resp = client.post("/api/v1/customers", headers=headers, json=create_payload)
    assert c_resp.status_code == 201
    cust_data = c_resp.json()["data"]
    cust_id = cust_data["id"]
    assert cust_data["name"] == "Aarav Patel"
    assert cust_data["email"] == "aarav@example.com"
    assert len(cust_data["phones"]) == 1
    assert cust_data["phones"][0]["normalized_phone"] == "+919876543210"

    # 3. Retrieve single customer
    g_resp = client.get(f"/api/v1/customers/{cust_id}", headers=headers)
    assert g_resp.status_code == 200
    assert g_resp.json()["data"]["id"] == cust_id

    # 4. Search customer
    s_resp = client.get("/api/v1/customers?search=Aarav", headers=headers)
    assert s_resp.status_code == 200
    assert s_resp.json()["total"] == 1

    s_resp2 = client.get("/api/v1/customers?search=9876543210", headers=headers)
    assert s_resp2.status_code == 200
    assert s_resp2.json()["total"] == 1

    # 5. Update customer
    p_resp = client.patch(f"/api/v1/customers/{cust_id}", headers=headers, json={"name": "Aarav P."})
    assert p_resp.status_code == 200
    assert p_resp.json()["data"]["name"] == "Aarav P."

    # 6. Delete customer as Org Admin
    admin_headers = auth_headers(org_admin_a)
    d_resp = client.delete(f"/api/v1/customers/{cust_id}", headers=admin_headers)
    assert d_resp.status_code == 204

    # Verify not found after deletion
    g_resp2 = client.get(f"/api/v1/customers/{cust_id}", headers=headers)
    assert g_resp2.status_code == 404
