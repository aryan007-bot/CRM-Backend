import json
from typing import Annotated, List, Optional

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

INSECURE_SECRET_DEFAULT = "default-insecure-secret-key-please-change-in-production-32chars"


def _parse_string_list(value: object) -> object:
    """Accepts a JSON array or a comma-separated string.

    `NoDecode` disables pydantic-settings' automatic JSON decoding for list
    fields, which otherwise rejects the plain `a,b` form that operators
    naturally write in `.env` files.
    """
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        return json.loads(stripped)
    return [item.strip() for item in stripped.split(",") if item.strip()]


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Recovery CRM API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | test | production
    LOG_LEVEL: str = "INFO"

    # Security
    SECRET_KEY: str = INSECURE_SECRET_DEFAULT
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/recovery_crm"
    TEST_DATABASE_URL: Optional[str] = None
    # Kept small on purpose: a blackholed database host must fail fast rather
    # than hang request handlers (and health checks) indefinitely.
    DB_CONNECT_TIMEOUT_SECONDS: int = 3

    # Valkey / Cache readiness.
    # Phase 1 uses no cache in the request path, so a missing Valkey must never
    # make a healthy application report itself as not-ready.
    VALKEY_URL: Optional[str] = "redis://localhost:6379/0"
    CACHE_REQUIRED_FOR_READINESS: bool = False

    # File Uploads
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024  # 25MB
    MAX_IMPORT_ROWS: int = 50000
    ALLOWED_EXTENSIONS: Annotated[List[str], NoDecode] = [".xlsx", ".csv"]

    # CORS — configured through ALLOWED_ORIGINS (falls back to CORS_ORIGINS).
    # Accepts "https://a.com,https://b.com" or a JSON array.
    ALLOWED_ORIGINS: Annotated[List[str], NoDecode] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        validation_alias=AliasChoices("ALLOWED_ORIGINS", "CORS_ORIGINS"),
    )

    # Rate limiting (in-process, per worker). Disabled automatically in tests.
    RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    UPLOAD_RATE_LIMIT_PER_MINUTE: int = 20

    # Uploaded spreadsheet files are staged under this directory (never
    # publicly served).
    FILE_STORAGE_PATH: str = "./storage/imports"
    EXPORTS_STORAGE_PATH: str = "./storage/exports"

    # Phase 3 Recovery Automation & Intelligence Settings
    ANALYSIS_TIMEOUT_SECONDS: int = 15
    DEFAULT_PAGE_SIZE: int = 25
    MAX_PAGE_SIZE: int = 100

    # Phase 4 Control Plane & Observability Settings
    MONITORING_ENABLED: bool = True
    HEALTH_CHECK_INTERVAL_SECONDS: int = 60
    PROVIDER_HEALTH_INTERVAL_SECONDS: int = 120
    METRICS_RETENTION_DAYS: int = 30
    EVENT_RETENTION_DAYS: int = 90
    ALERT_EVALUATION_INTERVAL_SECONDS: int = 30
    HEARTBEAT_TIMEOUT_SECONDS: int = 120
    MAX_ADMIN_ACTION_RATE: int = 60
    DEPLOYMENT_PROVIDER: str = "mock"
    SECRET_PROVIDER: str = "local"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_db_url(cls, value: object) -> object:
        if isinstance(value, str):
            if value.startswith("postgresql://") and not value.startswith("postgresql+"):
                return value.replace("postgresql://", "postgresql+psycopg://", 1)
            if value.startswith("postgres://"):
                return value.replace("postgres://", "postgresql+psycopg://", 1)
        return value

    @field_validator("ALLOWED_ORIGINS", "ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def _split_list_settings(cls, value: object) -> object:
        return _parse_string_list(value)


    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    def validate_for_startup(self) -> List[str]:
        """Returns a list of fatal configuration problems for this environment."""
        problems: List[str] = []

        if self.is_production:
            if self.SECRET_KEY == INSECURE_SECRET_DEFAULT or len(self.SECRET_KEY) < 32:
                problems.append(
                    "SECRET_KEY must be set to a unique value of at least 32 characters in production."
                )
            if "*" in self.ALLOWED_ORIGINS:
                problems.append(
                    "ALLOWED_ORIGINS must not contain '*' in production; list explicit origins."
                )
            if not self.ALLOWED_ORIGINS:
                problems.append("ALLOWED_ORIGINS must contain at least one origin in production.")
            if self.CACHE_REQUIRED_FOR_READINESS and not self.VALKEY_URL:
                problems.append(
                    "CACHE_REQUIRED_FOR_READINESS is enabled but VALKEY_URL is not configured."
                )

        return problems


settings = Settings()
