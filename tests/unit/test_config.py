from app.core.config import INSECURE_SECRET_DEFAULT, Settings


def test_allowed_origins_accepts_comma_separated_env(monkeypatch):
    """`.env` files use `a,b`; that must not require JSON."""
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com,https://admin.example.com")
    settings = Settings()
    assert settings.ALLOWED_ORIGINS == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def test_allowed_origins_accepts_json_array_env(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", '["https://app.example.com"]')
    assert Settings().ALLOWED_ORIGINS == ["https://app.example.com"]


def test_allowed_origins_accepts_empty_env(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    assert Settings().ALLOWED_ORIGINS == []


def test_legacy_cors_origins_name_still_works(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://legacy.example.com")
    assert Settings().ALLOWED_ORIGINS == ["https://legacy.example.com"]


def test_allowed_extensions_accepts_comma_separated_env(monkeypatch):
    monkeypatch.setenv("ALLOWED_EXTENSIONS", ".csv,.xlsx")
    assert Settings().ALLOWED_EXTENSIONS == [".csv", ".xlsx"]


def test_defaults_are_development_safe():
    settings = Settings()
    assert settings.ALLOWED_ORIGINS == ["http://localhost:3000", "http://127.0.0.1:3000"]
    assert settings.CACHE_REQUIRED_FOR_READINESS is False
    # Development may run with the insecure default; production may not (below).
    assert settings.validate_for_startup() == []


def test_production_rejects_default_secret_and_wildcard_cors(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    settings = Settings()

    problems = settings.validate_for_startup()
    assert any("SECRET_KEY" in problem for problem in problems)

    monkeypatch.setenv("SECRET_KEY", "a" * 48)
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    problems = Settings().validate_for_startup()
    assert any("ALLOWED_ORIGINS" in problem for problem in problems)

    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    assert Settings().validate_for_startup() == []


def test_production_rejects_empty_origins(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a" * 48)
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    problems = Settings().validate_for_startup()
    assert any("at least one origin" in problem for problem in problems)


def test_cache_required_without_valkey_is_rejected(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a" * 48)
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("CACHE_REQUIRED_FOR_READINESS", "true")
    monkeypatch.setenv("VALKEY_URL", "")
    problems = Settings().validate_for_startup()
    assert any("VALKEY_URL" in problem for problem in problems)


def test_insecure_default_is_flagged():
    """The shipped default secret must never satisfy production validation."""
    assert len(INSECURE_SECRET_DEFAULT) >= 32
    problems = Settings(ENVIRONMENT="production").validate_for_startup()
    assert any("SECRET_KEY" in problem for problem in problems)
