import uuid
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictException, NotFoundException
from app.db.models.audit import AuditLog
from app.db.models.creditor import Creditor
from app.schemas.creditor import CreditorCreate
from app.utils.pagination import paginate


class CreditorService:
    @staticmethod
    def list_creditors(
        db: Session,
        organization_id: uuid.UUID,
        search: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Creditor], int]:
        query = select(Creditor).where(Creditor.organization_id == organization_id)

        if status:
            query = query.where(Creditor.status == status)
        if search:
            query = query.where(Creditor.name.ilike(f"%{search.strip()}%"))

        query = query.order_by(Creditor.name.asc())
        return paginate(db, query, page=page, page_size=page_size)

    @staticmethod
    def get_creditor(db: Session, organization_id: uuid.UUID, creditor_id: uuid.UUID) -> Creditor:
        stmt = select(Creditor).where(
            Creditor.id == creditor_id,
            Creditor.organization_id == organization_id,
        )
        creditor = db.scalar(stmt)
        if not creditor:
            raise NotFoundException("Creditor not found", code="CREDITOR_NOT_FOUND")
        return creditor

    @staticmethod
    def create_creditor(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        data: CreditorCreate,
    ) -> Creditor:
        # Check duplicate name within organization
        existing = db.scalar(
            select(Creditor).where(
                Creditor.organization_id == organization_id,
                Creditor.name == data.name.strip(),
            )
        )
        if existing:
            raise ConflictException(f"Creditor '{data.name.strip()}' already exists", code="CREDITOR_EXISTS")

        creditor = Creditor(
            organization_id=organization_id,
            name=data.name.strip(),
            status=data.status,
        )
        db.add(creditor)
        db.flush()

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE_CREDITOR",
            entity_type="CREDITOR",
            entity_id=creditor.id,
        )
        db.add(audit)
        db.commit()
        db.refresh(creditor)
        return creditor
