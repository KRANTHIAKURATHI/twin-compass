"""
Self-contained identity provider - no Supabase, no network.

Credentials live in `local_credentials` (bcrypt). Access tokens are HS256
JWTs this backend signs and verifies with LOCAL_JWT_SECRET, carrying the same
claim shape Supabase issues (`sub`, `email`, `aud`, `exp`) so
`app/core/security.py` verifies both modes with one code path and the
frontend cannot tell the difference.

Refresh tokens are opaque 256-bit random strings; only their SHA-256 is
stored. Every redemption rotates: the presented token is marked used and a
new one issued. Re-presenting a used token is treated as a replay and
revokes the whole family, which is the standard containment response to a
stolen refresh token.

Password resets write a link to DATA_DIR/password-reset-links.log instead of
sending email, because "runs from files with nothing else installed" has to
include a way to actually complete the flow.
"""
from __future__ import annotations

import hashlib
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import anyio

from app.auth.providers.base import ProviderIdentity, ProviderTokens
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.logging import get_logger, log_security_event
from app.core.passwords import dummy_verify, hash_password, verify_password
from app.models.identity import AuthToken, LocalCredential, Profile

logger = get_logger(__name__)

REFRESH_KIND = "refresh"
RESET_KIND = "reset"

# After this many consecutive failures the account stops accepting passwords
# for LOCKOUT_SECONDS. Slows credential stuffing without a shared cache.
MAX_FAILED_ATTEMPTS = 10
LOCKOUT_SECONDS = 15 * 60


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; compare everything in UTC."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class LocalAuthProvider:
    name = "local"

    def __init__(self, session: AsyncSession):
        self._session = session
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Token minting
    # ------------------------------------------------------------------
    def _issue_access_token(self, profile_id: uuid.UUID, email: str) -> tuple[str, int]:
        now = int(time.time())
        exp = now + self._settings.ACCESS_TOKEN_TTL_SECONDS
        token = jwt.encode(
            {
                "sub": str(profile_id),
                "email": email,
                "aud": self._settings.LOCAL_JWT_AUDIENCE,
                "role": "authenticated",
                "iat": now,
                "exp": exp,
                "iss": "oncotwin-local",
            },
            self._settings.LOCAL_JWT_SECRET,
            algorithm="HS256",
        )
        return token, exp

    async def _issue_refresh_token(self, profile_id: uuid.UUID) -> str:
        raw = secrets.token_urlsafe(32)
        self._session.add(
            AuthToken(
                profile_id=profile_id,
                kind=REFRESH_KIND,
                token_hash=_hash_token(raw),
                expires_at=_now() + timedelta(seconds=self._settings.REFRESH_COOKIE_MAX_AGE_SECONDS),
            )
        )
        await self._session.flush()
        return raw

    async def _session_for(self, profile: Profile) -> ProviderTokens:
        access, exp = self._issue_access_token(profile.id, profile.email)
        refresh = await self._issue_refresh_token(profile.id)
        return ProviderTokens(access_token=access, refresh_token=refresh, expires_at=exp)

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------
    async def _profile_by_email(self, email: str) -> Profile | None:
        stmt = select(Profile).where(Profile.email == email.strip().lower())
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _credential(self, profile_id: uuid.UUID) -> LocalCredential | None:
        stmt = select(LocalCredential).where(LocalCredential.profile_id == profile_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------------
    # AuthProvider interface
    # ------------------------------------------------------------------
    async def create_user(self, *, email: str, password: str, full_name: str) -> ProviderIdentity:
        normalized = email.strip().lower()
        if await self._profile_by_email(normalized) is not None:
            raise ConflictError("An account with this email already exists.", field="email")

        profile_id = uuid.uuid4()
        # bcrypt is deliberately slow (~100ms); off the event loop it goes.
        password_hash = await anyio.to_thread.run_sync(hash_password, password)
        self._session.add(
            LocalCredential(profile_id=profile_id, password_hash=password_hash, email_verified=True)
        )
        return ProviderIdentity(id=profile_id, email=normalized)

    async def authenticate(self, *, email: str, password: str) -> tuple[ProviderIdentity, ProviderTokens]:
        generic = AuthenticationError("Invalid email or password.")
        profile = await self._profile_by_email(email)
        if profile is None:
            # Spend the same time as a real verification so the absence of an
            # account is not measurable from outside.
            await anyio.to_thread.run_sync(dummy_verify)
            raise generic

        credential = await self._credential(profile.id)
        if credential is None:
            await anyio.to_thread.run_sync(dummy_verify)
            raise generic

        locked_until = _aware(credential.locked_until)
        if locked_until and locked_until > _now():
            log_security_event(logger, "login.locked_out", email=email, profile_id=str(profile.id))
            raise AuthenticationError(
                "Too many failed sign-in attempts. Try again later or reset your password."
            )

        ok = await anyio.to_thread.run_sync(verify_password, password, credential.password_hash)
        if not ok:
            credential.failed_attempts += 1
            if credential.failed_attempts >= MAX_FAILED_ATTEMPTS:
                credential.locked_until = _now() + timedelta(seconds=LOCKOUT_SECONDS)
                log_security_event(
                    logger, "login.lockout_triggered", email=email, profile_id=str(profile.id)
                )
            await self._session.flush()
            log_security_event(logger, "login.failed", email=email)
            raise generic

        credential.failed_attempts = 0
        credential.locked_until = None
        tokens = await self._session_for(profile)
        return ProviderIdentity(id=profile.id, email=profile.email), tokens

    async def refresh(self, refresh_token: str) -> tuple[ProviderIdentity, ProviderTokens]:
        expired = AuthenticationError("Session expired. Please sign in again.")
        stmt = select(AuthToken).where(
            AuthToken.token_hash == _hash_token(refresh_token), AuthToken.kind == REFRESH_KIND
        )
        record = (await self._session.execute(stmt)).scalar_one_or_none()
        if record is None:
            raise expired

        if record.used_at is not None:
            # Replay of an already-rotated token: assume the token was stolen
            # and drop every live session for this user.
            log_security_event(
                logger, "refresh.replay_detected", profile_id=str(record.profile_id)
            )
            await self._revoke_all_refresh_tokens(record.profile_id)
            await self._session.flush()
            raise expired

        if record.revoked_at is not None or (_aware(record.expires_at) or _now()) <= _now():
            raise expired

        profile = await self._session.get(Profile, record.profile_id)
        if profile is None or not profile.is_active or profile.deleted_at is not None:
            raise expired

        record.used_at = _now()
        tokens = await self._session_for(profile)
        return ProviderIdentity(id=profile.id, email=profile.email), tokens

    async def revoke_session(self, *, access_token: str | None, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        stmt = select(AuthToken).where(
            AuthToken.token_hash == _hash_token(refresh_token), AuthToken.kind == REFRESH_KIND
        )
        record = (await self._session.execute(stmt)).scalar_one_or_none()
        if record is not None and record.revoked_at is None:
            record.revoked_at = _now()
            await self._session.flush()

    async def _revoke_all_refresh_tokens(self, profile_id: uuid.UUID) -> None:
        stmt = select(AuthToken).where(
            AuthToken.profile_id == profile_id,
            AuthToken.kind == REFRESH_KIND,
            AuthToken.revoked_at.is_(None),
        )
        for token in (await self._session.execute(stmt)).scalars():
            token.revoked_at = _now()

    async def request_password_reset(self, email: str) -> None:
        profile = await self._profile_by_email(email)
        if profile is None:
            return  # Silent: the caller returns the same response either way.

        raw = secrets.token_urlsafe(32)
        self._session.add(
            AuthToken(
                profile_id=profile.id,
                kind=RESET_KIND,
                token_hash=_hash_token(raw),
                expires_at=_now() + timedelta(seconds=self._settings.PASSWORD_RESET_TTL_SECONDS),
            )
        )
        await self._session.flush()

        link = f"{str(self._settings.PASSWORD_RESET_REDIRECT_URL).rstrip('/')}?token={raw}"
        target = self._settings.DATA_DIR / "password-reset-links.log"
        line = f"{_now().isoformat()}\t{profile.email}\t{link}\n"
        await anyio.to_thread.run_sync(
            lambda: target.open("a", encoding="utf-8").write(line)
        )
        logger.info(
            "password reset link written (local provider sends no email)",
            extra={"extra_fields": {"file": str(target), "email": profile.email}},
        )

    async def reset_password(self, *, token: str, new_password: str) -> None:
        invalid = AuthenticationError("This reset link is invalid or has expired. Request a new one.")
        stmt = select(AuthToken).where(
            AuthToken.token_hash == _hash_token(token), AuthToken.kind == RESET_KIND
        )
        record = (await self._session.execute(stmt)).scalar_one_or_none()
        if record is None or record.used_at is not None or record.revoked_at is not None:
            raise invalid
        if (_aware(record.expires_at) or _now()) <= _now():
            raise invalid

        credential = await self._credential(record.profile_id)
        if credential is None:
            raise invalid

        credential.password_hash = await anyio.to_thread.run_sync(hash_password, new_password)
        credential.password_changed_at = _now()
        credential.failed_attempts = 0
        credential.locked_until = None
        record.used_at = _now()
        # Changing a password must not leave older sessions alive.
        await self._revoke_all_refresh_tokens(record.profile_id)
        await self._session.flush()

    async def delete_user(self, user_id: uuid.UUID) -> None:
        credential = await self._credential(user_id)
        if credential is not None:
            await self._session.delete(credential)
            await self._session.flush()
