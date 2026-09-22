from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Engine setup
engine_args: dict = {
    "pool_pre_ping": True,
}

if "sqlite" in settings.DATABASE_URL:
    engine_args["connect_args"] = {"check_same_thread": False}
else:
    engine_args["pool_size"] = 10
    engine_args["max_overflow"] = 20
    # psycopg accepts connect_timeout directly. Without it, an unreachable host
    # (e.g. a firewalled IP address) blocks the connection attempt forever and
    # takes request handlers and health probes down with it.
    engine_args["connect_args"] = {"connect_timeout": settings.DB_CONNECT_TIMEOUT_SECONDS}

engine = create_engine(settings.DATABASE_URL, **engine_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Provide a transactional database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
