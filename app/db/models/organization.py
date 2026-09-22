from typing import TYPE_CHECKING, List

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.account import Account
    from app.db.models.campaign import Campaign
    from app.db.models.creditor import Creditor
    from app.db.models.customer import Customer
    from app.db.models.import_job import Import
    from app.db.models.user import User


class Organization(Base, IDMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active, suspended

    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    customers: Mapped[List["Customer"]] = relationship("Customer", back_populates="organization", cascade="all, delete-orphan")
    creditors: Mapped[List["Creditor"]] = relationship("Creditor", back_populates="organization", cascade="all, delete-orphan")
    accounts: Mapped[List["Account"]] = relationship("Account", back_populates="organization", cascade="all, delete-orphan")
    imports: Mapped[List["Import"]] = relationship("Import", back_populates="organization", cascade="all, delete-orphan")
    campaigns: Mapped[List["Campaign"]] = relationship("Campaign", back_populates="organization", cascade="all, delete-orphan")
