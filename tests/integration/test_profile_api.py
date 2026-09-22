from tests.conftest import auth_headers


def test_get_and_update_profile(client, supervisor_a):
    headers = auth_headers(supervisor_a)

    response = client.get("/api/v1/profile", headers=headers)
    assert response.status_code == 200
    profile = response.json()["data"]
    assert profile["email"] == "supervisor_a@alpha.com"
    assert profile["role"] == "SUPERVISOR"
    assert profile["organization_name"] == "Organization Alpha"

    updated = client.patch(
        "/api/v1/profile",
        headers=headers,
        json={"name": "Supervisor Renamed", "email": "supervisor.renamed@alpha.com"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "Supervisor Renamed"
    assert updated.json()["data"]["email"] == "supervisor.renamed@alpha.com"

    # Persisted, and the new identity can authenticate.
    refetched = client.get("/api/v1/profile", headers=headers)
    assert refetched.json()["data"]["email"] == "supervisor.renamed@alpha.com"

    relogin = client.post(
        "/api/v1/auth/login",
        json={"email": "supervisor.renamed@alpha.com", "password": "Password123!"},
    )
    assert relogin.status_code == 200
    assert relogin.json()["user"]["primary_role"] == "SUPERVISOR"


def test_profile_cannot_escalate_role(client, viewer_a):
    headers = auth_headers(viewer_a)

    response = client.patch(
        "/api/v1/profile",
        headers=headers,
        json={"name": "Climber", "role": "ORG_ADMIN", "primary_role": "SUPER_ADMIN"},
    )
    # Unknown fields are ignored, so the request succeeds but the role is unchanged.
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "VIEWER"

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["data"]["primary_role"] == "VIEWER"
    assert me.json()["data"]["roles"] == ["VIEWER"]

    # And the elevated capability is still denied.
    forbidden = client.post("/api/v1/customers", headers=headers, json={"name": "Nope"})
    assert forbidden.status_code == 403


def test_profile_email_must_be_unique_globally(client, supervisor_a, org_admin_b):
    headers = auth_headers(supervisor_a)

    conflict = client.patch(
        "/api/v1/profile",
        headers=headers,
        json={"email": "admin_b@beta.com"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "EMAIL_ALREADY_IN_USE"


def test_profile_requires_authentication(client):
    assert client.get("/api/v1/profile").status_code == 401
