"""
The identity-provider seam.

`AuthService` depends only on this interface, so swapping Supabase Auth for
the self-contained local provider (or, later, anything else) touches no
service, router, schema or test.

Providers own credentials and tokens ONLY. Application identity - the
`profiles` and `user_roles` rows, and therefore the user's role - is always
this backend's own concern, in both modes. That split is what keeps the API
contract identical no matter which provider is configured.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderTokens:
    """A freshly issued session from whichever provider is active."""

    access_token: str
    refresh_token: str
    expires_at: int  # unix seconds


@dataclass(frozen=True)
class ProviderIdentity:
    """The provider's view of a user - id plus email, nothing more."""

    id: uuid.UUID
    email: str


@dataclass(frozen=True)
class VerifiedToken:
    sub: str
    email: str | None
    exp: int


class AuthProvider(Protocol):
    """Credential and token operations. Implementations must be async-safe:
    any blocking network/CPU work has to be pushed off the event loop."""

    name: str

    async def create_user(self, *, email: str, password: str, full_name: str) -> ProviderIdentity:
        """Register a credential. Raises ConflictError if the email is taken."""

    async def authenticate(self, *, email: str, password: str) -> tuple[ProviderIdentity, ProviderTokens]:
        """Verify a password. Raises AuthenticationError on any failure."""

    async def refresh(self, refresh_token: str) -> tuple[ProviderIdentity, ProviderTokens]:
        """Exchange a refresh token for a new session, rotating the refresh token."""

    async def revoke_session(self, *, access_token: str | None, refresh_token: str | None) -> None:
        """Best-effort logout. Must never raise."""

    async def request_password_reset(self, email: str) -> None:
        """Start a reset. Must not reveal whether the account exists."""

    async def reset_password(self, *, token: str, new_password: str) -> None:
        """Complete a reset. Raises AuthenticationError on a bad/expired token."""

    async def delete_user(self, user_id: uuid.UUID) -> None:
        """Compensating action when profile creation fails after user creation."""
