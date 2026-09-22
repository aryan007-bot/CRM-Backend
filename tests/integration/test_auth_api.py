from tests.conftest import auth_headers


def test_auth_login_success(client, org_admin_a):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin_a@alpha.com", "password": "Password123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin_a@alpha.com"
    assert "ORG_ADMIN" in data["user"]["roles"]


def test_auth_login_wrong_password(client, org_admin_a):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin_a@alpha.com", "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "INVALID_CREDENTIALS"


def test_auth_login_nonexistent_user(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@alpha.com", "password": "Password123!"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "INVALID_CREDENTIALS"


def test_auth_get_me_success(client, supervisor_a):
    headers = auth_headers(supervisor_a)
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["email"] == supervisor_a.email
    assert "SUPERVISOR" in data["roles"]


def test_auth_get_me_unauthenticated(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "TOKEN_MISSING"


def test_auth_logout(client, supervisor_a):
    headers = auth_headers(supervisor_a)
    response = client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"
