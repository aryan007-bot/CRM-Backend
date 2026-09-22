import uuid
from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hashing():
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_create_and_decode():
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    role = "SUPERVISOR"

    token = create_access_token(user_id, org_id, role)
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == str(user_id)
    assert payload["org_id"] == str(org_id)
    assert payload["role"] == role


def test_jwt_expired():
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    role = "AGENT"

    # Create expired token
    token = create_access_token(user_id, org_id, role, expires_delta=timedelta(seconds=-10))
    payload = decode_access_token(token)

    assert payload is None


def test_jwt_invalid_string():
    payload = decode_access_token("not.a.valid.jwt.token")
    assert payload is None
