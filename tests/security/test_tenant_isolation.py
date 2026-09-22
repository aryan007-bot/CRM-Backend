import os

from tests.conftest import auth_headers


def test_strict_multi_tenant_isolation(client, supervisor_a, org_admin_b):
    headers_a = auth_headers(supervisor_a)
    headers_b = auth_headers(org_admin_b)

    # In Organization B, create Customer, Account, Campaign, and upload an Import
    cust_b_resp = client.post(
        "/api/v1/customers",
        headers=headers_b,
        json={"name": "Org B Secret Customer", "phones": [{"phone": "9988776655", "is_primary": True}]},
    )
    assert cust_b_resp.status_code == 201
    cust_b_id = cust_b_resp.json()["data"]["id"]

    acc_b_resp = client.post(
        "/api/v1/accounts",
        headers=headers_b,
        json={
            "customer_id": cust_b_id,
            "account_number": "ACC-SECRET-B",
            "outstanding_amount": 99999.00,
        },
    )
    assert acc_b_resp.status_code == 201
    acc_b_id = acc_b_resp.json()["data"]["id"]

    camp_b_resp = client.post(
        "/api/v1/campaigns",
        headers=headers_b,
        json={"name": "Org B Campaign"},
    )
    assert camp_b_resp.status_code == 201
    camp_b_id = camp_b_resp.json()["data"]["id"]

    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "valid-recovery.csv")
    with open(fixture_path, "rb") as f:
        imp_b_resp = client.post(
            "/api/v1/imports/upload",
            headers=headers_b,
            files={"file": ("valid.csv", f, "text/csv")},
        )
    assert imp_b_resp.status_code == 201
    imp_b_id = imp_b_resp.json()["data"]["import_id"]

    # NOW TEST THAT USER A (Organization A) CANNOT ACCESS ANY OF ORG B's DATA
    # 1. Access Customer B -> 404
    resp = client.get(f"/api/v1/customers/{cust_b_id}", headers=headers_a)
    assert resp.status_code == 404

    # 2. Access Account B -> 404
    resp = client.get(f"/api/v1/accounts/{acc_b_id}", headers=headers_a)
    assert resp.status_code == 404

    # 3. Access Campaign B -> 404
    resp = client.get(f"/api/v1/campaigns/{camp_b_id}", headers=headers_a)
    assert resp.status_code == 404

    # 4. Access Import B -> 404
    resp = client.get(f"/api/v1/imports/{imp_b_id}", headers=headers_a)
    assert resp.status_code == 404

    # 5. List Customers for User A -> Should not contain Customer B
    resp = client.get("/api/v1/customers", headers=headers_a)
    assert resp.status_code == 200
    ids_in_a = [item["id"] for item in resp.json()["items"]]
    assert cust_b_id not in ids_in_a
