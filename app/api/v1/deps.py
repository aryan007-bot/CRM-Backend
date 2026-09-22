import uuid
from typing import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenException, UnauthorizedException
from app.core.security import decode_access_token
from app.db.models.organization import Organization
from app.db.models.user import User
from app.db.session import get_db

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Extracts and validates JWT bearer token, resolving the current User."""
    if not credentials:
        raise UnauthorizedException("Missing authentication token", code="TOKEN_MISSING")

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise UnauthorizedException("Invalid or expired authentication token", code="TOKEN_INVALID")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedException("Invalid token payload", code="TOKEN_INVALID")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise UnauthorizedException("Invalid user identifier in token", code="TOKEN_INVALID")

    stmt = select(User).where(User.id == user_id)
    user = db.scalar(stmt)

    if not user or not user.is_active:
        raise UnauthorizedException("User account not found or inactive", code="USER_INACTIVE")

    # Verify organization is active
    org = db.scalar(select(Organization).where(Organization.id == user.organization_id))
    if not org or org.status != "active":
        raise UnauthorizedException("Organization is suspended or inactive", code="ORG_INACTIVE")

    return user


def require_role(*allowed_roles: str) -> Callable[[User], User]:
    """Dependency factory enforcing Role-Based Access Control (RBAC)."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_roles = current_user.roles

        # SUPER_ADMIN has system-wide permissions
        if "SUPER_ADMIN" in user_roles:
            return current_user

        # ORG_ADMIN has full permissions within their organization
        if "ORG_ADMIN" in user_roles and "SUPER_ADMIN" not in allowed_roles:
            return current_user

        # Check if user possesses any of the required roles
        for role in allowed_roles:
            if role in user_roles:
                return current_user

        raise ForbiddenException(
            f"Operation requires one of the following roles: {', '.join(allowed_roles)}",
            code="INSUFFICIENT_PERMISSIONS",
        )

    return role_checker
