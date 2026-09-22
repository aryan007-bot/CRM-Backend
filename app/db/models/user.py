import uuid
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.organization import Organization


class Role(Base, IDMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    # SUPER_ADMIN, ORG_ADMIN, SUPERVISOR, AI_MANAGER, AGENT, VIEWER

    user_roles: Mapped[List["UserRole"]] = relationship("UserRole", back_populates="role")


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="user_roles")
    role: Mapped["Role"] = relationship("Role", back_populates="user_roles")


class User(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Email is the login identity and is resolved without an organization
    # selector, so it must be globally unique. Anything weaker makes login
    # ambiguous and can authenticate a user into the wrong organization.
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")
    user_roles: Mapped[List["UserRole"]] = relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    @property
    def roles(self) -> List[str]:
        return [ur.role.name for ur in self.user_roles if ur.role]

    @property
    def primary_role(self) -> str:
        roles = self.roles
        if "SUPER_ADMIN" in roles:
            return "SUPER_ADMIN"
        if "ORG_ADMIN" in roles:
            return "ORG_ADMIN"
        if "SUPERVISOR" in roles:
            return "SUPERVISOR"
        if "AI_MANAGER" in roles:
            return "AI_MANAGER"
        if "AGENT" in roles:
            return "AGENT"
        return roles[0] if roles else "VIEWER"
