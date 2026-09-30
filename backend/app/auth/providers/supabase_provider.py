"""
Supabase Auth provider.

Two defects in the original inline implementation are fixed here.

1. Blocking calls. `supabase-py`'s client is synchronous; calling it directly
   from an `async def` handler blocks the whole event loop for the duration
   of the HTTP round-trip, so one slow Supabase call stalls every other
   in-flight request. All SDK calls now go through `anyio.to_thread.run_sync`.

2. Exception coverage. The original caught `AuthApiError`, but gotrue's
   client-side failures - `AuthSessionMissingError`, `AuthRetryableError`,
   `AuthInvalidCredentialsError` - derive from `CustomAuthError`, NOT from
   `AuthApiError`. They escaped the handler and surfaced as opaque 500s. The
   common base `AuthError` is caught instead, plus `SupabaseException` for a
   malformed/placeholder API key, which `create_client` raises eagerly.
"""
from __future__ import annotations

import uuid
from functools import lru_cache

import anyio
from gotrue.errors import AuthApiError, AuthError
from supabase import Client, create_client

try:  # import path differs across supabase-py 2.x point releases
    from supabase import SupabaseException  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    from supabase._sync.client import SupabaseException  # type: ignore[no-redef]

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ConflictError, UpstreamServiceError
from app.core.logging import get_logger, log_security_event

logger = get_logger(__name__)

# Errors that mean "the deployment is misconfigured", not "the user typed the
# wrong password" - surfaced as 502 so they are not mistaken for auth failures.
_CONFIG_ERRORS = (SupabaseException,)


async def verify_access_token_with_supabase(token: str):
    """Validate a bearer token with Supabase Auth instead of a local JWT secret."""
    from app.auth.providers.base import ProviderIdentity

    def _call():
        return _anon_client().auth.get_user(token)

    try:
        result = await anyio.to_thread.run_sync(_call)
    except (AuthError, *_CONFIG_ERRORS) as exc:
        raise AuthenticationError("Invalid or expired session token.") from exc
    if result.user is None:
        raise AuthenticationError("Invalid or expired session token.")
    return ProviderIdentity(id=uuid.UUID(result.user.id), email=result.user.email or "")


@lru_cache
def _anon_client() -> Client:
    s = get_settings()
    try:
        return create_client(str(s.SUPABASE_URL), s.SUPABASE_ANON_KEY)  # type: ignore[arg-type]
    except _CONFIG_ERRORS as exc:
        raise UpstreamServiceError(
            f"Supabase is not configured correctly: {exc}. Check SUPABASE_URL / SUPABASE_ANON_KEY."
        ) from exc


def get_admin_client() -> Client:
    """Service-role client for server-only operations (e.g. Storage).

    Never expose this client, or the key behind it, to the frontend - it
    bypasses RLS entirely.
    """
    return _admin_client()


@lru_cache
def _admin_client() -> Client:
    s = get_settings()
    try:
        return create_client(str(s.SUPABASE_URL), s.SUPABASE_SERVICE_ROLE_KEY)  # type: ignore[arg-type]
    except _CONFIG_ERRORS as exc:
        raise UpstreamServiceError(
            f"Supabase is not configured correctly: {exc}. Check SUPABASE_SERVICE_ROLE_KEY."
        ) from exc


def _is_already_registered(exc: AuthError) -> bool:
    message = str(getattr(exc, "message", exc)).lower()
    return "already" in message and ("registered" in message or "exists" in message)


class SupabaseAuthProvider:
    name = "supabase"

    def __init__(self) -> None:
        self._settings = get_settings()

    async def create_user(self, *, email: str, password: str, full_name: str):
        from app.auth.providers.base import ProviderIdentity

        def _call():
            # Registration is performed server-side so new local accounts are
            # confirmed immediately and Supabase does not send a verification
            # email. The service-role key never reaches the browser.
            return _admin_client().auth.admin.create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {"full_name": full_name},
                }
            )

        try:
            result = await anyio.to_thread.run_sync(_call)
        except AuthError as exc:
            if _is_already_registered(exc):
                raise ConflictError("An account with this email already exists.", field="email") from exc
            raise UpstreamServiceError(f"Registration failed: {exc}") from exc
        except _CONFIG_ERRORS as exc:
            raise UpstreamServiceError(f"Supabase is not configured correctly: {exc}") from exc

        if result.user is None:
            raise UpstreamServiceError("Registration failed: no user returned by the identity provider.")
        return ProviderIdentity(id=uuid.UUID(result.user.id), email=email.strip().lower())

    async def authenticate(self, *, email: str, password: str):
        from app.auth.providers.base import ProviderIdentity, ProviderTokens

        def _call():
            return _anon_client().auth.sign_in_with_password({"email": email, "password": password})

        try:
            result = await anyio.to_thread.run_sync(_call)
        except AuthError as exc:
            log_security_event(logger, "login.failed", email=email, reason=str(exc))
            raise AuthenticationError("Invalid email or password.") from exc
        except _CONFIG_ERRORS as exc:
            raise UpstreamServiceError(f"Supabase is not configured correctly: {exc}") from exc

        if result.session is None or result.user is None:
            raise AuthenticationError("Invalid email or password.")
        return (
            ProviderIdentity(id=uuid.UUID(result.user.id), email=result.user.email or email),
            ProviderTokens(
                access_token=result.session.access_token,
                refresh_token=result.session.refresh_token,
                expires_at=_expires_at(result.session),
            ),
        )

    async def refresh(self, refresh_token: str):
        from app.auth.providers.base import ProviderIdentity, ProviderTokens

        def _call():
            return _anon_client().auth.refresh_session(refresh_token)

        try:
            result = await anyio.to_thread.run_sync(_call)
        except AuthError as exc:
            raise AuthenticationError("Session expired. Please sign in again.") from exc
        except _CONFIG_ERRORS as exc:
            raise UpstreamServiceError(f"Supabase is not configured correctly: {exc}") from exc

        if result.session is None or result.user is None:
            raise AuthenticationError("Session expired. Please sign in again.")
        return (
            ProviderIdentity(id=uuid.UUID(result.user.id), email=result.user.email or ""),
            ProviderTokens(
                access_token=result.session.access_token,
                refresh_token=result.session.refresh_token,
                expires_at=_expires_at(result.session),
            ),
        )

    async def revoke_session(self, *, access_token: str | None, refresh_token: str | None) -> None:
        if not access_token:
            return

        def _call():
            _admin_client().auth.admin.sign_out(access_token)

        try:
            await anyio.to_thread.run_sync(_call)
        except (AuthError, *_CONFIG_ERRORS) as exc:
            # Logout must succeed for the caller regardless; the cookie is
            # cleared by the router either way.
            logger.warning("supabase sign_out failed", extra={"extra_fields": {"error": str(exc)}})

    async def request_password_reset(self, email: str) -> None:
        def _call():
            _anon_client().auth.reset_password_for_email(
                email, {"redirect_to": str(self._settings.PASSWORD_RESET_REDIRECT_URL)}
            )

        try:
            await anyio.to_thread.run_sync(_call)
        except (AuthError, *_CONFIG_ERRORS) as exc:
            # Never surfaced: the endpoint's response is identical whether or
            # not the address exists, so it cannot be used for enumeration.
            logger.info("forgot_password upstream response", extra={"extra_fields": {"note": str(exc)}})

    async def reset_password(self, *, token: str, new_password: str) -> None:
        def _call():
            s = get_settings()
            client = create_client(str(s.SUPABASE_URL), s.SUPABASE_ANON_KEY)  # type: ignore[arg-type]
            # A recovery link yields a one-use session; act as that session so
            # Supabase's own rule (a recovery token may only update its own
            # user) applies. An expired token makes set_session raise
            # AuthSessionMissingError - an AuthError, now caught below.
            client.auth.set_session(token, token)
            client.auth.update_user({"password": new_password})

        try:
            await anyio.to_thread.run_sync(_call)
        except (AuthError, *_CONFIG_ERRORS) as exc:
            raise AuthenticationError(
                "This reset link is invalid or has expired. Request a new one."
            ) from exc

    async def delete_user(self, user_id: uuid.UUID) -> None:
        def _call():
            _admin_client().auth.admin.delete_user(str(user_id))

        try:
            await anyio.to_thread.run_sync(_call)
        except (AuthError, AuthApiError, *_CONFIG_ERRORS) as exc:
            logger.warning(
                "could not roll back supabase user",
                extra={"extra_fields": {"user_id": str(user_id), "error": str(exc)}},
            )


def _expires_at(session) -> int:
    """Supabase may omit expires_at; fall back to the token's own exp claim."""
    value = getattr(session, "expires_at", None)
    if value:
        return int(value)
    import jwt as _jwt

    claims = _jwt.decode(session.access_token, options={"verify_signature": False})
    return int(claims["exp"])
