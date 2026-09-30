"""
Auth dependencies - "deny by default" plus role-based authorization.

`get_current_user` is the single place a bearer token becomes a resolved
application user with a role.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import TokenClaims, verify_access_token
from app.core.config import get_settings
from app.auth.providers.supabase_provider import verify_access_token_with_supabase
from app.db.session import get_db_session
from app.repositories.profile_repository import ProfileRepository
from app.schemas.auth import UserRole


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    email: str | None
    role: UserRole


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError("Missing or malformed Authorization header.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise AuthenticationError("Missing or malformed Authorization header.")
    return token


async def get_current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> CurrentUser:
    """Resolve the caller from an access token.

    Two checks, in order: verify the JWT's signature and expiry (no I/O),
    then resolve the application role from `profiles` / `user_roles`. The
    role deliberately is not read from a token claim - that would require a
    provider-side hook to inject custom claims, which neither run mode can
    assume is configured. The `user_roles(profile_id)` index keeps the
    lookup to one cheap indexed query.
    """
    token = _extract_bearer_token(authorization)
    if get_settings().uses_supabase:
        provider_identity = await verify_access_token_with_supabase(token)
        profile_id = provider_identity.id
    else:
        claims: TokenClaims = verify_access_token(token)
        try:
            profile_id = uuid.UUID(claims.sub)
        except (ValueError, AttributeError, TypeError) as exc:
            raise AuthenticationError("Invalid or expired session token.") from exc


    repo = ProfileRepository(session)
    profile = await repo.get_by_id(profile_id)
    if profile is None or not profile.is_active:
        raise AuthenticationError("Account not found or inactive.")

    role_name = profile.primary_role_name
    if role_name is None:
        raise AuthenticationError("This account has no assigned role. Contact an administrator.")

    return CurrentUser(id=profile.id, email=profile.email, role=role_name)  # type: ignore[arg-type]


def require_roles(*allowed: UserRole):
    """Dependency factory: `Depends(require_roles("admin"))`."""

    async def _dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed:
            raise AuthorizationError(f"This action requires one of: {', '.join(allowed)}.")
        return user

    return _dependency
