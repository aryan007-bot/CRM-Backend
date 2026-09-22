import uuid
from typing import List, Optional, Tuple

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundException, ValidationException
from app.db.models.audit import AuditLog
from app.db.models.customer import Customer, CustomerPhone
from app.import_engine.normalizer import normalize_phone
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.utils.pagination import paginate


class CustomerService:
    @staticmethod
    def list_customers(
        db: Session,
        organization_id: uuid.UUID,
        search: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "created_at",
        sort_direction: str = "desc",
    ) -> Tuple[List[Customer], int]:
        query = select(Customer).where(Customer.organization_id == organization_id)

        if status:
            query = query.where(Customer.status == status)

        if search:
            s = f"%{search.strip()}%"
            # Join phone to search across name, email, and phone
            query = query.outerjoin(Customer.phones).where(
                or_(
                    Customer.name.ilike(s),
                    Customer.email.ilike(s),
                    CustomerPhone.phone.ilike(s),
                    CustomerPhone.normalized_phone.ilike(s),
                )
            ).distinct()

        # Sorting
        sort_column = getattr(Customer, sort_by, Customer.created_at)
        if sort_direction.lower() == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        return paginate(db, query, page=page, page_size=page_size)

    @staticmethod
    def get_customer(db: Session, organization_id: uuid.UUID, customer_id: uuid.UUID) -> Customer:
        stmt = select(Customer).where(
            Customer.id == customer_id,
            Customer.organization_id == organization_id,
        )
        customer = db.scalar(stmt)
        if not customer:
            raise NotFoundException("Customer not found", code="CUSTOMER_NOT_FOUND")
        return customer

    @staticmethod
    def create_customer(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        data: CustomerCreate,
    ) -> Customer:
        customer = Customer(
            organization_id=organization_id,
            name=data.name.strip(),
            email=str(data.email).strip().lower() if data.email else None,
            status=data.status,
        )
        db.add(customer)
        db.flush()

        if data.phones:
            for phone_in in data.phones:
                norm, err = normalize_phone(phone_in.phone)
                if err:
                    raise ValidationException(f"Invalid phone number: {err}")
                phone_record = CustomerPhone(
                    customer_id=customer.id,
                    phone=phone_in.phone.strip(),
                    normalized_phone=norm,
                    phone_type=phone_in.phone_type,
                    is_primary=phone_in.is_primary,
                )
                db.add(phone_record)

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE_CUSTOMER",
            entity_type="CUSTOMER",
            entity_id=customer.id,
        )
        db.add(audit)
        db.commit()
        db.refresh(customer)
        return customer

    @staticmethod
    def update_customer(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        customer_id: uuid.UUID,
        data: CustomerUpdate,
    ) -> Customer:
        customer = CustomerService.get_customer(db, organization_id, customer_id)

        if data.name is not None:
            customer.name = data.name.strip()
        if data.email is not None:
            customer.email = str(data.email).strip().lower()
        if data.status is not None:
            customer.status = data.status

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="UPDATE_CUSTOMER",
            entity_type="CUSTOMER",
            entity_id=customer.id,
        )
        db.add(audit)
        db.commit()
        db.refresh(customer)
        return customer

    @staticmethod
    def delete_customer(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        customer_id: uuid.UUID,
    ) -> None:
        customer = CustomerService.get_customer(db, organization_id, customer_id)
        db.delete(customer)

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="DELETE_CUSTOMER",
            entity_type="CUSTOMER",
            entity_id=customer_id,
        )
        db.add(audit)
        db.commit()
