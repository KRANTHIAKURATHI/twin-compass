"""
Pydantic v2 request/response contracts for the auth module.

These shapes are deliberately written to serialize to EXACTLY the frontend's
`AuthUser` / `AuthSession` / `MutationResult<T>` interfaces in
`src/types/models.ts` — that file states plainly "Backend teams should treat
these interfaces as the API contract," so field names/casing/optionality
here are not incidental, they were copied from that file.
"""
from __future__ import annotations

import uuid
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.passwords import validate_password

# Roles a user may request for themselves at self-registration time.
# "admin" is deliberately excluded — see AuthService.register in
# app/services/auth_service.py for the enforced security rule and
# docs/module-1-auth-summary.md for the rationale.
SelfServeRole = Literal["doctor", "patient", "researcher"]
UserRole = Literal["doctor", "patient", "researcher", "admin"]


class Credentials(BaseModel):
    """Login input. The password is length-bounded but NOT policy-checked:
    an account created before a policy change must still be able to sign in
    (and report a clean 401, not a 422 that leaks the policy)."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(Credentials):
    name: str = Field(min_length=1, max_length=255)
    role: SelfServeRole = "doctor"
    hospital: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=255)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        # Single shared policy (app/core/passwords.py), identical to the one
        # reset-password enforces. Previously the two disagreed, so a user
        # could reset their way to a password registration would have refused.
        return validate_password(v)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Name cannot be blank.")
        return cleaned

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, description="Recovery token from the reset link.")
    password: str = Field(min_length=1, max_length=128)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        return validate_password(v)


class ProfileUpdateRequest(BaseModel):
    """PATCH /users/profile — only self-editable, non-privileged fields.

    Aliased to camelCase on the wire to match `AuthUser`'s own convention
    and the frontend's `UserService.updateProfile` contract exactly
    (`src/services/contracts.ts`) — `avatarUrl` in, `avatar_url` internally.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    title: str | None = Field(default=None, max_length=255)
    hospital: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=1024, validation_alias="avatarUrl")


class AuthUser(BaseModel):
    """Matches `src/types/models.ts` -> AuthUser exactly."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    name: str = Field(validation_alias="full_name", serialization_alias="name")
    email: EmailStr
    role: UserRole
    title: str | None = None
    hospital: str | None = None
    avatarUrl: str | None = Field(default=None, validation_alias="avatar_url", serialization_alias="avatarUrl")


class AuthSession(BaseModel):
    """Matches `src/types/models.ts` -> AuthSession exactly.

    Deliberately has NO refresh-token field — the refresh token never
    touches JavaScript. It travels only in an httpOnly cookie set alongside
    this JSON body. See app/api/v1/routers/auth.py.
    """

    user: AuthUser
    accessToken: str
    expiresAt: str  # ISO-8601, matches frontend's `ISODate` alias


T = TypeVar("T")


class MutationResult(BaseModel, Generic[T]):
    """Matches `src/types/models.ts` -> MutationResult<T> exactly."""

    ok: bool
    data: T | None = None
    message: str | None = None
