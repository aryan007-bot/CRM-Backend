def test_health_liveness(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_reports_ready_without_valkey(client, monkeypatch):
    """PostgreSQL is required for readiness; the optional cache must not gate it.

    No Valkey instance is running here, so if the cache gated readiness a
    deployment without a cache would never report ready.
    """
    from app.main import SessionLocal as app_session_local
    from tests.conftest import TestingSessionLocal

    # The probe deliberately uses its own session (so a dead database returns a
    # clean 503 rather than a 500 from a failed dependency).
    monkeypatch.setattr("app.main.SessionLocal", TestingSessionLocal)
    assert app_session_local is not None

    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["database"] == "connected"


def test_ready_is_503_when_database_unreachable(client, monkeypatch):
    """A dead database must degrade readiness, not raise a 500 or hang."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Point the probe at a closed port with a 1s connect timeout so the check
    # fails fast instead of waiting on the real database host.
    dead_engine = create_engine(
        "postgresql+psycopg://postgres:postgres@127.0.0.1:1/recovery_crm",
        connect_args={"connect_timeout": 1},
    )
    monkeypatch.setattr("app.main.SessionLocal", sessionmaker(bind=dead_engine))

    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "disconnected"
    dead_engine.dispose()
