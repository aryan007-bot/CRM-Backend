from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.db import session as db_session
from app.db.models.queue import QueueMetricSnapshot
from app.db.models.security_event import OperationalEvent
from app.db.models.service import ServiceHealthLog


def run_retention_cleanup_sync() -> Dict[str, Any]:
    """Cleans up expired health logs, queue metric snapshots, and operational events."""
    db: Session = db_session.SessionLocal()
    summary: Dict[str, Any] = {
        "deleted_health_logs": 0,
        "deleted_queue_metrics": 0,
        "deleted_operational_events": 0,
    }

    try:
        metrics_cutoff = datetime.now(timezone.utc) - timedelta(days=settings.METRICS_RETENTION_DAYS)
        events_cutoff = datetime.now(timezone.utc) - timedelta(days=settings.EVENT_RETENTION_DAYS)

        # 1. Health logs
        res1 = db.execute(delete(ServiceHealthLog).where(ServiceHealthLog.checked_at < metrics_cutoff))
        summary["deleted_health_logs"] = res1.rowcount or 0

        # 2. Queue metrics
        res2 = db.execute(delete(QueueMetricSnapshot).where(QueueMetricSnapshot.captured_at < metrics_cutoff))
        summary["deleted_queue_metrics"] = res2.rowcount or 0

        # 3. Operational events
        res3 = db.execute(delete(OperationalEvent).where(OperationalEvent.timestamp < events_cutoff))
        summary["deleted_operational_events"] = res3.rowcount or 0

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Retention cleanup error: {e}")
        summary["error"] = str(e)
    finally:
        db.close()

    return summary
