import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictException, NotFoundException, UnauthorizedException
from app.core.security import create_access_token, verify_password
from app.db.models.audit import AuditLog
from app.db.models.organization import Organization
from app.db.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.schemas.profile import ProfileOut, ProfileUpdate


class AuthService:
    @staticmethod
    def authenticate_user(db: Session, login_data: LoginRequest) -> TokenResponse:
        # Look up user by email (globally unique — see migration b41c9a7f2e10).
        stmt = select(User).where(User.email == login_data.email.lower().strip())
        user = db.scalar(stmt)

        if not user or not verify_password(login_data.password, user.password_hash):
            # Same message and code for "unknown email" and "wrong password" so
            # the response cannot be used to enumerate accounts.
            raise UnauthorizedException("Invalid email or password", code="INVALID_CREDENTIALS")

        if not user.is_active:
            raise UnauthorizedException("Account has been deactivated", code="ACCOUNT_INACTIVE")

        # Check organization status
        org = db.scalar(select(Organization).where(Organization.id == user.organization_id))
        if not org or org.status != "active":
            raise UnauthorizedException("Organization is suspended or inactive", code="ORG_INACTIVE")

        token = create_access_token(
            subject=user.id,
            organization_id=user.organization_id,
            role=user.primary_role,
        )

        # Audit log login
        audit = AuditLog(
            organization_id=user.organization_id,
            user_id=user.id,
            action="USER_LOGIN",
            entity_type="USER",
            entity_id=user.id,
        )
        db.add(audit)
        db.commit()

        user_out = UserOut(
            id=user.id,
            organization_id=user.organization_id,
            name=user.name,
            email=user.email,
            roles=user.roles,
            primary_role=user.primary_role,
            is_active=user.is_active,
            created_at=user.created_at,
        )

        return TokenResponse(access_token=token, token_type="bearer", user=user_out)

    @staticmethod
    def get_profile(db: Session, user_id: uuid.UUID) -> ProfileOut:
        user = db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise NotFoundException("User not found")

        org = db.scalar(select(Organization).where(Organization.id == user.organization_id))
        org_name = org.name if org else "Unknown Organization"

        return ProfileOut(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.primary_role,
            organization_id=user.organization_id,
            organization_name=org_name,
        )

    @staticmethod
    def update_profile(db: Session, user_id: uuid.UUID, update_data: ProfileUpdate) -> ProfileOut:
        user = db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise NotFoundException("User not found")

        if update_data.name is not None:
            user.name = update_data.name.strip()

        if update_data.email is not None:
            new_email = update_data.email.lower().strip()
            # Email is the login identity, so the conflict check is global.
            existing = db.scalar(
                select(User).where(
                    User.email == new_email,
                    User.id != user.id,
                )
            )
            if existing:
                raise ConflictException("Email already in use", code="EMAIL_ALREADY_IN_USE")
            user.email = new_email

        db.commit()
        db.refresh(user)

        return AuthService.get_profile(db, user_id)
