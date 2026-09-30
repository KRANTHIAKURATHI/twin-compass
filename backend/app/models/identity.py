"""
Identity models - Roles, Profiles, UserRoles, plus the two tables the local
(non-Supabase) auth provider needs.

Implements Database Architecture Blueprint Sections 3.1-3.3, with one
deliberate, documented extension: a fourth role, `patient`, alongside
`doctor` / `admin` / `researcher`, because the finalized frontend contract
(`src/types/models.ts`, `UserRole = "doctor" | "patient" | "researcher" |
"admin"`) and the built Patient Portal route guards committed to a four-role
model. That is an additive row in a reference table, not a schema redesign.

`Profile` never stores a credential. In `supabase` mode Supabase Auth
(`auth.users`) is the credential store; in `local` mode credentials live in
`LocalCredential`, which is a separate table on purpose so that switching
providers cannot accidentally expose or orphan password material.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk

# The seeded reference rows. Ids are fixed so migrations, fixtures and tests
# can rely on them.
SEED_ROLES: tuple[tuple[int, str, str], ...] = (
    (1, "doctor", "Clinician with full patient/twin/prediction access."),
    (2, "admin", "Platform/hospital administrator."),
    (3, "researcher", "Read-only, de-identified aggregate access."),
    (4, "patient", "Patient portal user - own-record access only."),
)


class Role(Base):
    """Reference table of system roles. Never deleted - see Database Blueprint 3.2."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))

    user_roles: Mapped[list["UserRole"]] = relationship(back_populates="role")


class Profile(TimestampMixin, Base):
    """Application-level identity record.

    In supabase mode `id` is the SAME UUID as the corresponding
    `auth.users.id` row - a 1:1 extension table, not a separate identity
    (Database Blueprint 3.1). In local mode this backend allocates the UUID
    itself and `LocalCredential` hangs off it.
    """

    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = uuid_pk()
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    hospital: Mapped[str | None] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(255))
    license_number: Mapped[str | None] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # `foreign_keys` is REQUIRED on both sides: user_roles has two FKs back to
    # profiles.id (profile_id and granted_by), so without it SQLAlchemy cannot
    # pick a join condition and raises AmbiguousForeignKeysError the first time
    # any mapper is configured - i.e. on the first real query.
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        foreign_keys="UserRole.profile_id",
    )
    credential: Mapped["LocalCredential | None"] = relationship(
        back_populates="profile", cascade="all, delete-orphan", uselist=False
    )

    @property
    def primary_role_name(self) -> str | None:
        """v1 assumes one role per user (matching the frontend's singular
        `AuthUser.role`). The schema supports more; this picks the
        earliest-granted role until the product needs true multi-role support."""
        if not self.user_roles:
            return None
        return sorted(self.user_roles, key=lambda ur: ur.granted_at)[0].role.name


class UserRole(Base):
    """Many-to-many join between Profile and Role (Database Blueprint 3.3)."""

    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("profile_id", "role_id", name="uq_user_roles_profile_role"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("roles.id"), nullable=False)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    profile: Mapped["Profile"] = relationship(back_populates="user_roles", foreign_keys=[profile_id])
    role: Mapped["Role"] = relationship(back_populates="user_roles")


class LocalCredential(TimestampMixin, Base):
    """Password material for AUTH_PROVIDER=local. Unused in supabase mode.

    Kept out of `profiles` deliberately: a profile row is safe to return from
    a query or serialize by accident, and a password hash should never ride
    along with it.
    """

    __tablename__ = "local_credentials"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    profile: Mapped["Profile"] = relationship(back_populates="credential")


class AuthToken(TimestampMixin, Base):
    """Refresh and password-reset tokens for AUTH_PROVIDER=local.

    Only the SHA-256 of each token is stored, so a database leak does not
    hand over usable sessions. Refresh tokens are rotated on every use:
    redeeming one marks it used and issues a replacement, which makes replay
    of a captured token detectable and cheap to shut down.
    """

    __tablename__ = "auth_tokens"
    __table_args__ = (Index("ix_auth_tokens_profile_kind", "profile_id", "kind"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # "refresh" | "reset"
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped["Profile"] = relationship()
