import uuid
from sqlalchemy.orm import Session
from app.db import session as db_session
from app.services.recovery.analysis import PostCallAnalysisService


def run_call_analysis_sync(organization_id: uuid.UUID, call_id: uuid.UUID) -> None:
    db: Session = db_session.SessionLocal()
    try:
        PostCallAnalysisService.analyze_call(db, organization_id, call_id)
    finally:
        db.close()
