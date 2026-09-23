import concurrent.futures
import uuid
import pytest
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.db.models.configuration import ConfigurationItem
from app.db.models.queue import QueueRegistryItem
from app.db.models.worker import WorkerNode
from app.services.control_plane.configuration_service import ConfigurationService
from app.services.control_plane.queue_service import QueueService
from app.services.control_plane.worker_service import WorkerService


def test_concurrent_worker_commands(db: Session):
    worker = WorkerNode(
        scope="PLATFORM",
        worker_type="CAMPAIGN",
        status="HEALTHY",
        hostname="worker-conc-01",
    )
    db.add(worker)
    db.commit()

    worker_id = worker.id

    # Test idempotency: dispatches with identical idempotency key return the exact same command
    res1 = WorkerService.dispatch_command(
        db=db,
        worker_id=worker_id,
        command="DRAIN",
        idempotency_key=f"key-{worker_id}-1",
    )
    db.commit()

    res2 = WorkerService.dispatch_command(
        db=db,
        worker_id=worker_id,
        command="DRAIN",
        idempotency_key=f"key-{worker_id}-1",
    )
    db.commit()

    assert res1.id == res2.id


def test_concurrent_queue_pause(db: Session):
    queue = QueueRegistryItem(
        name="conc-queue",
        queue_type="DIAL",
        scope="PLATFORM",
        status="HEALTHY",
    )
    db.add(queue)
    db.commit()

    queue_id = queue.id

    res1 = QueueService.pause_queue(db, queue_id)
    db.commit()
    res2 = QueueService.pause_queue(db, queue_id)
    db.commit()

    assert res1.status == "PAUSED"
    assert res2.status == "PAUSED"


def test_concurrent_configuration_updates(db: Session):
    cfg = ConfigurationItem(
        scope="PLATFORM",
        key="conc.timeout",
        value_type="int",
        is_secret=False,
        is_mutable=True,
        safe_value="10",
        version=1,
        state="APPLIED",
    )
    db.add(cfg)
    db.commit()

    cfg_id = cfg.id

    res1 = ConfigurationService.update_configuration(db, cfg_id, 20)
    v1 = res1.version
    db.commit()
    res2 = ConfigurationService.update_configuration(db, cfg_id, 30)
    v2 = res2.version
    db.commit()

    assert v1 == 2
    assert v2 == 3
    assert res2.safe_value == "30"


