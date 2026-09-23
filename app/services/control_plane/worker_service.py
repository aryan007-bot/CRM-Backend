from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import InvalidStateTransitionException, NotFoundException
from app.db.models.audit import AuditLog
from app.db.models.worker import WorkerCommand, WorkerNode
from app.services.control_plane.event_bus import event_bus


class WorkerService:
    """Manages worker registration, heartbeat, commands, and timeout tracking."""

    @staticmethod
    def record_heartbeat(
        db: Session,
        worker_id: uuid.UUID,
        status: str = "HEALTHY",
        active_jobs: int = 0,
        concurrency: Optional[int] = None,
        version: Optional[str] = None,
    ) -> WorkerNode:
        worker = db.scalar(select(WorkerNode).where(WorkerNode.id == worker_id))
        now = datetime.now(timezone.utc)

        if not worker:
            worker = WorkerNode(
                id=worker_id,
                scope="SERVICE",
                worker_type="CAMPAIGN",
                status=status,
                version=version or "1.0.0",
                environment=settings.ENVIRONMENT,
                hostname=f"worker-{str(worker_id)[:8]}",
                concurrency=concurrency or 5,
                active_jobs=active_jobs,
                last_heartbeat_at=now,
                started_at=now,
            )
            db.add(worker)
        else:
            worker.status = status
            worker.active_jobs = active_jobs
            if concurrency is not None:
                worker.concurrency = concurrency
            if version is not None:
                worker.version = version
            worker.last_heartbeat_at = now

        db.flush()
        return worker

    @staticmethod
    def dispatch_command(
        db: Session,
        worker_id: uuid.UUID,
        command: str,
        requested_by: Optional[uuid.UUID] = None,
        idempotency_key: Optional[str] = None,
    ) -> WorkerCommand:
        worker = db.scalar(select(WorkerNode).where(WorkerNode.id == worker_id))
        if not worker:
            raise NotFoundException(f"Worker {worker_id} not found", code="WORKER_NOT_FOUND")

        # Idempotency check
        if idempotency_key:
            existing = db.scalar(
                select(WorkerCommand).where(
                    WorkerCommand.worker_id == worker_id,
                    WorkerCommand.idempotency_key == idempotency_key,
                )
            )
            if existing:
                return existing

        now = datetime.now(timezone.utc)
        cmd_record = WorkerCommand(
            worker_id=worker_id,
            command=command,
            requested_by=requested_by,
            status="ACKNOWLEDGED",
            requested_at=now,
            acknowledged_at=now,
            idempotency_key=idempotency_key,
        )
        db.add(cmd_record)

        # Apply state transitions
        if command == "DRAIN":
            worker.status = "DRAINING"
        elif command == "RESUME":
            worker.status = "HEALTHY"
        elif command == "RESTART":
            worker.status = "STARTING"
            cmd_record.status = "COMPLETED"
            cmd_record.completed_at = now
            worker.status = "HEALTHY"
        elif command == "DISABLE":
            worker.status = "STOPPED"
        else:
            raise InvalidStateTransitionException(f"Unknown worker command: {command}")

        # Audit log
        audit = AuditLog(
            organization_id=worker.organization_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
            user_id=requested_by,
            action=f"WORKER_{command}_REQUESTED",
            entity_type="worker_node",
            entity_id=worker.id,
            metadata_json={"command": command, "new_status": worker.status},
        )
        db.add(audit)

        # Operational event
        event_bus.emit_operational_event(
            db=db,
            event_type=f"worker.{command.lower()}",
            scope=worker.scope,
            organization_id=worker.organization_id,
            entity_type="worker",
            entity_id=str(worker.id),
            severity="INFO",
            message=f"Worker {worker.id} received command {command}",
            payload={"command": command, "status": worker.status},
        )

        db.flush()
        return cmd_record

    @staticmethod
    def check_worker_timeouts(db: Session) -> int:
        """Finds workers whose heartbeat has expired and flags them DEGRADED/STOPPED."""
        timeout_delta = timedelta(seconds=settings.HEARTBEAT_TIMEOUT_SECONDS)
        cutoff = datetime.now(timezone.utc) - timeout_delta

        expired_workers = db.scalars(
            select(WorkerNode).where(
                WorkerNode.status.in_(["HEALTHY", "STARTING", "DRAINING"]),
                WorkerNode.last_heartbeat_at < cutoff,
            )
        ).all()

        count = 0
        for w in expired_workers:
            w.status = "DEGRADED"
            count += 1
            event_bus.emit_operational_event(
                db=db,
                event_type="worker.degraded",
                scope=w.scope,
                organization_id=w.organization_id,
                entity_type="worker",
                entity_id=str(w.id),
                severity="WARNING",
                message=f"Worker {w.id} heartbeat timed out",
                payload={"last_heartbeat_at": w.last_heartbeat_at.isoformat() if w.last_heartbeat_at else None},
            )

        if count > 0:
            db.flush()
        return count
