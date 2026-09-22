from typing import TYPE_CHECKING, List

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.account import Account
    from app.db.models.organization import Organization


class Creditor(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "creditors"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_creditor_org_name"),
        Index("idx_creditor_org_name", "organization_id", "name"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active, inactive

    organization: Mapped["Organization"] = relationship("Organization", back_populates="creditors")
    accounts: Mapped[List["Account"]] = relationship("Account", back_populates="creditor")
