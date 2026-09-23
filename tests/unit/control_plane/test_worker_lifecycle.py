from datetime import datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.worker import WorkerCommand, WorkerNode
from app.services.control_plane.worker_service import WorkerService


def test_worker_heartbeat_and_update(db: Session):
    worker_id = uuid.uuid4()
    worker = WorkerService.record_heartbeat(
        db=db,
        worker_id=worker_id,
        status="HEALTHY",
        active_jobs=2,
        concurrency=10,
        version="1.0.1",
    )
    assert worker.id == worker_id
    assert worker.status == "HEALTHY"
    assert worker.active_jobs == 2
    assert worker.concurrency == 10
    assert worker.version == "1.0.1"

    # Update heartbeat
    worker_up = WorkerService.record_heartbeat(
        db=db,
        worker_id=worker_id,
        status="HEALTHY",
        active_jobs=5,
    )
    assert worker_up.active_jobs == 5


def test_worker_command_dispatch_and_idempotency(db: Session):
    worker_id = uuid.uuid4()
    WorkerService.record_heartbeat(db=db, worker_id=worker_id, status="HEALTHY")

    # Dispatch drain command
    idemp_key = f"drain-{worker_id}"
    cmd1 = WorkerService.dispatch_command(
        db=db,
        worker_id=worker_id,
        command="DRAIN",
        idempotency_key=idemp_key,
    )
    assert cmd1.status == "ACKNOWLEDGED"
    worker = db.scalar(select(WorkerNode).where(WorkerNode.id == worker_id))
    assert worker.status == "DRAINING"

    # Idempotent second call returns same command record
    cmd2 = WorkerService.dispatch_command(
        db=db,
        worker_id=worker_id,
        command="DRAIN",
        idempotency_key=idemp_key,
    )
    assert cmd2.id == cmd1.id


def test_worker_heartbeat_timeout(db: Session):
    worker_id = uuid.uuid4()
    WorkerService.record_heartbeat(db=db, worker_id=worker_id, status="HEALTHY")

    # Manually backdate the heartbeat
    worker = db.scalar(select(WorkerNode).where(WorkerNode.id == worker_id))
    worker.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=200)
    db.commit()

    timed_out = WorkerService.check_worker_timeouts(db)
    assert timed_out >= 1

    db.refresh(worker)
    assert worker.status == "DEGRADED"
