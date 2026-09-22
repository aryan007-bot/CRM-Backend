from tests.conftest import auth_headers


def test_creditors_paginated_envelope_and_crud(client, supervisor_a):
    headers = auth_headers(supervisor_a)

    # Empty list still uses the standard paginated envelope.
    empty = client.get("/api/v1/creditors", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "page": 1, "page_size": 25, "total": 0}

    create_resp = client.post(
        "/api/v1/creditors",
        headers=headers,
        json={"name": "Bajaj Finance", "status": "active"},
    )
    assert create_resp.status_code == 201
    creditor_id = create_resp.json()["data"]["id"]

    # Duplicate name within the organization is rejected.
    dup = client.post("/api/v1/creditors", headers=headers, json={"name": "Bajaj Finance"})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "CREDITOR_EXISTS"

    detail = client.get(f"/api/v1/creditors/{creditor_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["name"] == "Bajaj Finance"

    listed = client.get("/api/v1/creditors", headers=headers)
    body = listed.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 25
    assert body["items"][0]["id"] == creditor_id

    filtered = client.get("/api/v1/creditors?search=Bajaj", headers=headers)
    assert filtered.json()["total"] == 1

    unmatched = client.get("/api/v1/creditors?search=Nothing", headers=headers)
    assert unmatched.json()["total"] == 0


def test_creditor_not_found_and_tenant_scoped(client, supervisor_a, org_admin_b):
    headers_a = auth_headers(supervisor_a)
    headers_b = auth_headers(org_admin_b)

    created = client.post("/api/v1/creditors", headers=headers_b, json={"name": "Org B Lender"})
    assert created.status_code == 201
    creditor_b_id = created.json()["data"]["id"]

    # Same organization: readable. Other organization: invisible.
    assert client.get(f"/api/v1/creditors/{creditor_b_id}", headers=headers_b).status_code == 200
    assert client.get(f"/api/v1/creditors/{creditor_b_id}", headers=headers_a).status_code == 404

    listed_a = client.get("/api/v1/creditors", headers=headers_a)
    assert listed_a.json()["total"] == 0
