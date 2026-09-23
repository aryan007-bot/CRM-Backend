from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundException
from app.db.models.audit import AuditLog
from app.db.models.dial_queue import DialQueueItem
from app.db.models.export_job import ExportJob
from app.db.models.queue import QueueMetricSnapshot, QueueRegistryItem
from app.services.control_plane.event_bus import event_bus


class QueueService:
    """Manages queue registration, metrics collection, and pause/resume control."""

    @staticmethod
    def ensure_default_queues(db: Session):
        standard_queues = [
            ("dial-queue", "DIAL", "Dial queue for automated campaign calls"),
            ("analysis-queue", "ANALYSIS", "Post-call AI analysis queue"),
            ("followup-queue", "FOLLOW_UP", "Follow-up SMS/WhatsApp automation queue"),
            ("export-queue", "EXPORT", "Async CRM export generation queue"),
        ]
        for name, q_type, ref in standard_queues:
            existing = db.scalar(select(QueueRegistryItem).where(QueueRegistryItem.name == name))
            if not existing:
                queue = QueueRegistryItem(
                    scope="PLATFORM",
                    name=name,
                    queue_type=q_type,
                    status="HEALTHY",
                    backend_reference_safe=ref,
                )
                db.add(queue)
        db.flush()

    @staticmethod
    def capture_metrics_snapshot(db: Session, queue_id: uuid.UUID) -> QueueMetricSnapshot:
        queue = db.scalar(select(QueueRegistryItem).where(QueueRegistryItem.id == queue_id))
        if not queue:
            raise NotFoundException(f"Queue {queue_id} not found", code="QUEUE_NOT_FOUND")

        pending = 0
        running = 0
        failed = 0
        retrying = 0
        dead = 0

        if queue.queue_type == "DIAL":
            pending = db.scalar(select(func.count(DialQueueItem.id)).where(DialQueueItem.status == "pending")) or 0
            running = db.scalar(select(func.count(DialQueueItem.id)).where(DialQueueItem.status == "in_progress")) or 0
            failed = db.scalar(select(func.count(DialQueueItem.id)).where(DialQueueItem.status == "failed")) or 0
        elif queue.queue_type == "EXPORT":
            pending = db.scalar(select(func.count(ExportJob.id)).where(ExportJob.status == "queued")) or 0
            running = db.scalar(select(func.count(ExportJob.id)).where(ExportJob.status == "processing")) or 0
            failed = db.scalar(select(func.count(ExportJob.id)).where(ExportJob.status == "failed")) or 0

        now = datetime.now(timezone.utc)
        snapshot = QueueMetricSnapshot(
            queue_id=queue_id,
            pending=pending,
            running=running,
            retrying=retrying,
            failed=failed,
            dead=dead,
            throughput=max(0, running * 2),
            oldest_job_age_seconds=10 if pending > 0 else 0,
            worker_count=2,
            latency_ms=15,
            captured_at=now,
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    @staticmethod
    def pause_queue(db: Session, queue_id: uuid.UUID, requested_by: Optional[uuid.UUID] = None) -> QueueRegistryItem:
        queue = db.scalar(select(QueueRegistryItem).where(QueueRegistryItem.id == queue_id))
        if not queue:
            raise NotFoundException(f"Queue {queue_id} not found", code="QUEUE_NOT_FOUND")

        queue.status = "PAUSED"

        audit = AuditLog(
            organization_id=queue.organization_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
            user_id=requested_by,
            action="QUEUE_PAUSED",
            entity_type="queue",
            entity_id=queue.id,
            metadata_json={"status": "PAUSED"},
        )
        db.add(audit)

        event_bus.emit_operational_event(
            db=db,
            event_type="queue.paused",
            scope=queue.scope,
            organization_id=queue.organization_id,
            entity_type="queue",
            entity_id=str(queue.id),
            severity="WARNING",
            message=f"Queue {queue.name} paused",
        )
        db.flush()
        return queue

    @staticmethod
    def resume_queue(db: Session, queue_id: uuid.UUID, requested_by: Optional[uuid.UUID] = None) -> QueueRegistryItem:
        queue = db.scalar(select(QueueRegistryItem).where(QueueRegistryItem.id == queue_id))
        if not queue:
            raise NotFoundException(f"Queue {queue_id} not found", code="QUEUE_NOT_FOUND")

        queue.status = "HEALTHY"

        audit = AuditLog(
            organization_id=queue.organization_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
            user_id=requested_by,
            action="QUEUE_RESUMED",
            entity_type="queue",
            entity_id=queue.id,
            metadata_json={"status": "HEALTHY"},
        )
        db.add(audit)

        event_bus.emit_operational_event(
            db=db,
            event_type="queue.resumed",
            scope=queue.scope,
            organization_id=queue.organization_id,
            entity_type="queue",
            entity_id=str(queue.id),
            severity="INFO",
            message=f"Queue {queue.name} resumed",
        )
        db.flush()
        return queue
