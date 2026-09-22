import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import logger
from app.db.models.user import Role
from app.db.session import SessionLocal
from app.utils.valkey import check_valkey_health

SYSTEM_ROLES = ["SUPER_ADMIN", "ORG_ADMIN", "SUPERVISOR", "AI_MANAGER", "AGENT", "VIEWER"]


def seed_roles() -> None:
    """Ensure standard system roles exist in the database."""
    try:
        with SessionLocal() as db:
            existing = set(db.scalars(select(Role.name)).all())
            to_add = [Role(name=r) for r in SYSTEM_ROLES if r not in existing]
            if to_add:
                db.add_all(to_add)
                db.commit()
                logger.info(f"Seeded {len(to_add)} system roles")
    except Exception as e:
        logger.warning(f"Could not seed roles (database may not be initialized yet): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    problems = settings.validate_for_startup()
    if problems:
        # Fail fast: shipping the default signing key or a wildcard CORS policy
        # to production is worse than refusing to boot.
        for problem in problems:
            logger.error(f"Invalid configuration: {problem}")
        raise RuntimeError("Refusing to start with invalid configuration: " + "; ".join(problems))

    logger.info(f"Starting up {settings.PROJECT_NAME} ({settings.ENVIRONMENT})...")
    seed_roles()
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Register error handlers
register_error_handlers(app)

# CORS Middleware — explicit origins only, configured through ALLOWED_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start_time = time.perf_counter()

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    response.headers["X-Request-ID"] = request_id

    # Never log request bodies or Authorization headers here.
    logger.info(
        f"{request.method} {request.url.path} - {response.status_code} ({duration_ms}ms)",
        extra={
            "request_id": request_id,
            "route": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )

    return response


@app.get("/health", tags=["Health"])
def health():
    """Liveness probe: the application process is running and serving traffic."""
    return {"status": "ok", "version": settings.VERSION}


@app.get("/ready", tags=["Health"])
def ready():
    """Readiness probe: required dependencies are reachable.

    PostgreSQL is always required. Valkey is only required when
    CACHE_REQUIRED_FOR_READINESS is enabled, because Phase 1 has no cache in the
    request path and must not report itself unhealthy without one.
    """
    db_healthy = False
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            db_healthy = True
    except Exception as e:
        logger.error(f"Database readiness check failed: {e}")

    valkey_healthy, valkey_msg = check_valkey_health()

    is_ready = db_healthy and (valkey_healthy or not settings.CACHE_REQUIRED_FOR_READINESS)
    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "degraded",
            "database": "connected" if db_healthy else "disconnected",
            "valkey": valkey_msg,
        },
    )


# Mount v1 router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)
