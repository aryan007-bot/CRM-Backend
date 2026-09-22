import uuid
from typing import Optional
from sqlalchemy.orm import Session
from app.db import session as db_session
from app.services.recovery.exports import ExportService


def run_export_job_sync(job_id: uuid.UUID) -> None:
    db: Session = db_session.SessionLocal()
    try:
        ExportService.process_export(db, job_id)
    finally:
        db.close()
