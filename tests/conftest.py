import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.models.organization import Organization
from app.db.models.user import Role, User, UserRole
from app.db.session import get_db
from app.main import app

settings.ENVIRONMENT = "test"

TEST_SQLITE_URL = os.environ.get("TEST_DATABASE_URL") or "sqlite:///file:testdb?mode=memory&cache=shared&uri=true"

_is_sqlite = TEST_SQLITE_URL.startswith("sqlite")
_test_engine_args = {"connect_args": {"check_same_thread": False, "uri": True}} if _is_sqlite else {}
_test_pool = StaticPool if _is_sqlite else None
if _test_pool is not None:
    _test_engine_args["poolclass"] = StaticPool

test_engine = create_engine(TEST_SQLITE_URL, **_test_engine_args)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

from app.db import session as db_session
db_session.SessionLocal = TestingSessionLocal


@pytest.fixture(autouse=True)
def clean_db():
    """Create fresh tables for every test and drop after test completes."""
    Base.metadata.create_all(bind=test_engine)
    with TestingSessionLocal() as session:
        roles = ["SUPER_ADMIN", "ORG_ADMIN", "SUPERVISOR", "AI_MANAGER", "AGENT", "VIEWER"]
        for r in roles:
            existing = session.scalar(select(Role).where(Role.name == r))
            if not existing:
                session.add(Role(name=r))
        session.commit()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    """Provide a clean database session per test function."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def test_org_a(db: Session) -> Organization:
    org = Organization(name="Organization Alpha", slug=f"alpha-{uuid.uuid4().hex[:6]}", status="active")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def test_org_b(db: Session) -> Organization:
    org = Organization(name="Organization Beta", slug=f"beta-{uuid.uuid4().hex[:6]}", status="active")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def create_user_with_role(db: Session, org_id: uuid.UUID, email: str, password: str, role_name: str) -> User:
    role = db.scalar(select(Role).where(Role.name == role_name))
    if not role:
        role = Role(name=role_name)
        db.add(role)
        db.flush()

    user = User(
        organization_id=org_id,
        name=f"User {role_name}",
        email=email.lower().strip(),
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)
    db.flush()

    user_role = UserRole(user_id=user.id, role_id=role.id)
    db.add(user_role)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def org_admin_a(db: Session, test_org_a: Organization) -> User:
    return create_user_with_role(db, test_org_a.id, "admin_a@alpha.com", "Password123!", "ORG_ADMIN")


@pytest.fixture
def supervisor_a(db: Session, test_org_a: Organization) -> User:
    return create_user_with_role(db, test_org_a.id, "supervisor_a@alpha.com", "Password123!", "SUPERVISOR")


@pytest.fixture
def viewer_a(db: Session, test_org_a: Organization) -> User:
    return create_user_with_role(db, test_org_a.id, "viewer_a@alpha.com", "Password123!", "VIEWER")


@pytest.fixture
def org_admin_b(db: Session, test_org_b: Organization) -> User:
    return create_user_with_role(db, test_org_b.id, "admin_b@beta.com", "Password123!", "ORG_ADMIN")


def auth_headers(user: User) -> dict:
    token = create_access_token(
        subject=user.id,
        organization_id=user.organization_id,
        role=user.primary_role,
    )
    return {"Authorization": f"Bearer {token}"}
