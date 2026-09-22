from tests.conftest import auth_headers


def test_rbac_viewer_restricted_from_mutations(client, viewer_a, supervisor_a):
    headers_viewer = auth_headers(viewer_a)
    headers_supervisor = auth_headers(supervisor_a)

    # 1. Viewer can read customers
    read_resp = client.get("/api/v1/customers", headers=headers_viewer)
    assert read_resp.status_code == 200

    # 2. Viewer cannot create customer -> 403
    create_resp = client.post(
        "/api/v1/customers",
        headers=headers_viewer,
        json={"name": "Forbidden Customer"},
    )
    assert create_resp.status_code == 403
    assert create_resp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # 3. Viewer cannot create campaign -> 403
    camp_resp = client.post(
        "/api/v1/campaigns",
        headers=headers_viewer,
        json={"name": "Forbidden Campaign"},
    )
    assert camp_resp.status_code == 403

    # 4. Supervisor CAN create customer -> 201
    super_create = client.post(
        "/api/v1/customers",
        headers=headers_supervisor,
        json={"name": "Allowed Customer"},
    )
    assert super_create.status_code == 201
    cust_id = super_create.json()["data"]["id"]

    # 5. Supervisor cannot delete customer (only ORG_ADMIN can) -> 403
    del_resp = client.delete(f"/api/v1/customers/{cust_id}", headers=headers_supervisor)
    assert del_resp.status_code == 403
