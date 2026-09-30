"""
AuthService - the one place registration/login/reset business rules live.
Routers parse HTTP and delegate here; the identity provider behind it is an
injected dependency, so this file is identical in both run modes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.auth.providers.base import AuthProvider, ProviderTokens
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError, ConflictError, UpstreamServiceError
from app.core.logging import get_logger, log_security_event
from app.repositories.profile_repository import ProfileRepository
from app.schemas.auth import AuthSession, AuthUser, MutationResult, RegisterRequest

logger = get_logger(__name__)

# Roles that may never be granted through public self-registration. Enforced
# server-side regardless of what the client sends, on top of the schema-level
# Literal that already excludes it.
PRIVILEGED_ROLES = {"admin"}


def _to_auth_user(profile, role_name: str) -> AuthUser:
    return AuthUser(
        id=profile.id,
        name=profile.full_name,
        email=profile.email,
        role=role_name,  # type: ignore[arg-type]
        title=profile.title,
        hospital=profile.hospital,
        avatarUrl=profile.avatar_url,
    )


def _session_payload(profile, role_name: str, tokens: ProviderTokens) -> AuthSession:
    return AuthSession(
        user=_to_auth_user(profile, role_name),
        accessToken=tokens.access_token,
        expiresAt=datetime.fromtimestamp(tokens.expires_at, tz=timezone.utc).isoformat(),
    )


class AuthService:
    def __init__(self, repo: ProfileRepository, provider: AuthProvider):
        self._repo = repo
        self._provider = provider
        self._settings = get_settings()

    # ------------------------------------------------------------------
    async def register(self, payload: RegisterRequest) -> MutationResult[AuthUser]:
        if payload.role in PRIVILEGED_ROLES:
            log_security_event(
                logger, "register.privileged_role_rejected", email=payload.email, requested_role=payload.role
            )
            raise AuthorizationError(
                "The 'admin' role cannot be self-assigned at registration. "
                "Ask an existing administrator to grant it after your account is created.",
                field="role",
            )

        if await self._repo.get_by_email(payload.email) is not None:
            raise ConflictError("An account with this email already exists.", field="email")

        identity = await self._provider.create_user(
            email=payload.email, password=payload.password, full_name=payload.name
        )

        try:
            profile = await self._repo.create_profile_with_role(
                profile_id=identity.id,
                full_name=payload.name,
                email=identity.email,
                role_name=payload.role,
                hospital=payload.hospital,
                title=payload.title,
            )
            await self._repo.commit()
        except Exception:
            await self._repo.rollback()
            # Compensate: drop the credential we just created so the address
            # is free to retry. Without this the user is wedged - the profile
            # lookup finds nothing, but the provider refuses the email as
            # already registered. (The original code left this orphan behind
            # and documented it as a known limitation.)
            try:
                await self._provider.delete_user(identity.id)
                await self._repo.commit()
            except Exception:  # pragma: no cover - best effort only
                logger.exception("could not roll back provider user after failed profile write")
            logger.exception(
                "profile creation failed after provider user was created",
                extra={"extra_fields": {"user_id": str(identity.id)}},
            )
            raise UpstreamServiceError("Registration could not be completed. Please try again.") from None

        logger.info(
            "user registered",
            extra={"extra_fields": {"user_id": str(profile.id), "role": payload.role}},
        )
        return MutationResult(
            ok=True,
            data=_to_auth_user(profile, payload.role),
            message="Account created. You can sign in now.",
        )

    # ------------------------------------------------------------------
    async def login(self, email: str, password: str) -> tuple[AuthSession, str]:
        """Returns (AuthSession for the body, refresh token for the cookie)."""
        identity, tokens = await self._provider.authenticate(email=email, password=password)

        profile = await self._repo.get_by_id(identity.id)
        if profile is None or not profile.is_active:
            log_security_event(logger, "login.no_active_profile", email=email, user_id=str(identity.id))
            raise AuthenticationError("This account is not fully set up. Contact an administrator.")

        role_name = profile.primary_role_name
        if role_name is None:
            raise AuthenticationError("This account has no assigned role. Contact an administrator.")

        await self._repo.commit()  # persist token rows / lockout counters
        logger.info("user logged in", extra={"extra_fields": {"user_id": str(profile.id), "role": role_name}})
        return _session_payload(profile, role_name, tokens), tokens.refresh_token

    # ------------------------------------------------------------------
    async def refresh(self, refresh_token: str) -> tuple[AuthSession, str]:
        identity, tokens = await self._provider.refresh(refresh_token)

        profile = await self._repo.get_by_id(identity.id)
        if profile is None or not profile.is_active:
            raise AuthenticationError("This account is not fully set up. Contact an administrator.")
        role_name = profile.primary_role_name
        if role_name is None:
            raise AuthenticationError("This account has no assigned role. Contact an administrator.")

        await self._repo.commit()
        return _session_payload(profile, role_name, tokens), tokens.refresh_token

    # ------------------------------------------------------------------
    async def logout(self, access_token: str | None, refresh_token: str | None = None) -> MutationResult:
        await self._provider.revoke_session(access_token=access_token, refresh_token=refresh_token)
        await self._repo.commit()
        return MutationResult(ok=True, message="Signed out.")

    # ------------------------------------------------------------------
    async def forgot_password(self, email: str) -> MutationResult:
        await self._provider.request_password_reset(email)
        await self._repo.commit()
        # Identical response whether or not the address exists.
        return MutationResult(
            ok=True, message="If an account exists for that email, a reset link has been sent."
        )

    # ------------------------------------------------------------------
    async def reset_password(self, token: str, new_password: str) -> MutationResult:
        await self._provider.reset_password(token=token, new_password=new_password)
        await self._repo.commit()
        return MutationResult(ok=True, message="Password updated. You can now sign in.")

    # ------------------------------------------------------------------
    async def get_current_user(self, profile_id: uuid.UUID) -> AuthUser:
        profile = await self._repo.get_by_id(profile_id)
        if profile is None or not profile.is_active:
            raise AuthenticationError("Account not found or inactive.")
        role_name = profile.primary_role_name
        if role_name is None:
            raise AuthenticationError("This account has no assigned role. Contact an administrator.")
        return _to_auth_user(profile, role_name)

    # ------------------------------------------------------------------
    async def update_profile(self, profile_id: uuid.UUID, **fields: object) -> AuthUser:
        profile = await self._repo.get_by_id(profile_id)
        if profile is None or not profile.is_active:
            raise AuthenticationError("Account not found or inactive.")

        # Only fields the client actually sent are forwarded (the router
        # passes exclude_unset), and only these keys are writable - role,
        # email, is_active and id are not reachable from this endpoint.
        writable = {
            "full_name": fields.get("name"),
            "title": fields.get("title"),
            "hospital": fields.get("hospital"),
            "department": fields.get("department"),
            "avatar_url": fields.get("avatar_url"),
        }
        profile = await self._repo.update_profile(profile, **writable)
        await self._repo.commit()

        role_name = profile.primary_role_name
        if role_name is None:
            raise AuthenticationError("This account has no assigned role. Contact an administrator.")
        return _to_auth_user(profile, role_name)
