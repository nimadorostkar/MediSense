"""Dependency injection: db session, current user, RBAC guards (spec §8)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.errors import AuthError, ForbiddenError
from app.security.oidc import User, validate_token
from app.security.rbac import Permission, has_permission


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for s in get_session():
        yield s


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


async def current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Required authentication — raises 401 if no valid bearer token."""
    token = _extract_bearer(authorization)
    if not token:
        raise AuthError("Missing bearer token")
    return validate_token(token)


async def optional_user(
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    """Best-effort identity for the open chat surface (existing UI is unauth'd).

    Returns the authenticated user when a token is present, else None so the
    endpoint can still serve a read-only suggestion (never a commit)."""
    token = _extract_bearer(authorization)
    if not token:
        return None
    try:
        return validate_token(token)
    except AuthError:
        return None


def require(permission: Permission):
    """Dependency factory enforcing a single permission from the RBAC matrix."""

    async def _guard(user: Annotated[User, Depends(current_user)]) -> User:
        if not has_permission(user.role, permission):
            raise ForbiddenError(
                f"Role '{user.role}' lacks permission '{permission}'"
            )
        return user

    return _guard


SessionDep = Annotated[AsyncSession, Depends(db_session)]
CurrentUser = Annotated[User, Depends(current_user)]
OptionalUser = Annotated[User | None, Depends(optional_user)]
