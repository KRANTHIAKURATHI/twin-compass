"""Composition root: wires the configured provider + repositories into services."""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.providers.base import AuthProvider
from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.profile_repository import ProfileRepository
from app.services.auth_service import AuthService


def get_profile_repository(session: AsyncSession = Depends(get_db_session)) -> ProfileRepository:
    return ProfileRepository(session)


def get_auth_provider(session: AsyncSession = Depends(get_db_session)) -> AuthProvider:
    """Selected once per request from AUTH_PROVIDER.

    The local provider needs the request's DB session (it stores credentials
    and refresh tokens in the same transaction as the profile write, so a
    failed registration rolls both back together). The Supabase provider is
    stateless with respect to our database.
    """
    if get_settings().uses_supabase:
        from app.auth.providers.supabase_provider import SupabaseAuthProvider

        return SupabaseAuthProvider()  # type: ignore[return-value]

    from app.auth.providers.local_provider import LocalAuthProvider

    return LocalAuthProvider(session)  # type: ignore[return-value]


def get_auth_service(
    repo: ProfileRepository = Depends(get_profile_repository),
    provider: AuthProvider = Depends(get_auth_provider),
) -> AuthService:
    return AuthService(repo, provider)
