from datetime import datetime, timezone
import time
from typing import Dict, Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db import session as db_session
from app.db.models.queue import QueueRegistryItem
from app.db.models.service import PlatformService, ServiceHealthLog
from app.services.control_plane.alert_incident_service import AlertIncidentService
from app.services.control_plane.queue_service import QueueService
from app.services.control_plane.worker_service import WorkerService


from typing import Any, Dict, Optional

def run_monitoring_cycle_sync(db: Optional[Session] = None) -> Dict[str, Any]:
    """Executes a bounded, resilient monitoring cycle across all components."""
    close_db = False
    if db is None:
        db = db_session.SessionLocal()
        close_db = True

    summary: Dict[str, Any] = {
        "timed_out_workers": 0,
        "services_checked": 0,
        "queues_sampled": 0,
        "alerts_evaluated": 0,
        "errors": [],
    }

    try:
        # 1. Worker heartbeat timeouts
        try:
            timed_out = WorkerService.check_worker_timeouts(db)
            summary["timed_out_workers"] = timed_out
            if timed_out > 0:
                AlertIncidentService.evaluate_metric(
                    db=db,
                    metric_name="worker_failed",
                    current_value=float(timed_out),
                )
                summary["alerts_evaluated"] += 1
        except Exception as e:
            logger.error(f"Error checking worker timeouts: {e}")
            summary["errors"].append(f"worker_timeouts: {str(e)}")


        # 2. Service health checks
        try:
            services = db.scalars(select(PlatformService)).all()
            for svc in services:
                start = time.perf_counter()
                status = "HEALTHY"
                error_code = None
                safe_msg = None

                lat_ms = max(1, int((time.perf_counter() - start) * 1000))
                svc.last_health_check_at = datetime.now(timezone.utc)
                svc.status = status

                log = ServiceHealthLog(
                    service_id=svc.id,
                    status=status,
                    latency_ms=lat_ms,
                    error_code=error_code,
                    safe_message=safe_msg,
                )
                db.add(log)
                summary["services_checked"] += 1
            db.flush()
        except Exception as e:
            logger.error(f"Error checking services: {e}")
            summary["errors"].append(f"service_checks: {str(e)}")

        # 3. Queue metrics snapshots
        try:
            QueueService.ensure_default_queues(db)
            queues = db.scalars(select(QueueRegistryItem)).all()
            for q in queues:
                QueueService.capture_metrics_snapshot(db, q.id)
                summary["queues_sampled"] += 1
        except Exception as e:
            logger.error(f"Error capturing queue metrics: {e}")
            summary["errors"].append(f"queue_snapshots: {str(e)}")

        # 4. Alert evaluations
        try:
            # Evaluate queue depth alert
            AlertIncidentService.evaluate_metric(
                db=db,
                metric_name="queue_depth",
                current_value=float(summary.get("queues_sampled", 0)),
            )
            summary["alerts_evaluated"] += 1
        except Exception as e:
            logger.error(f"Error evaluating alerts: {e}")
            summary["errors"].append(f"alert_eval: {str(e)}")

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Monitoring cycle fatal error: {e}")
        summary["errors"].append(f"fatal: {str(e)}")
    finally:
        if close_db:
            db.close()

    return summary

