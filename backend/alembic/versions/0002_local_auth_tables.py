"""Module 1b: credential + token tables for the local (non-Supabase) provider

Revision ID: 0002_local_auth
Revises: 0001_identity

These two tables are used only when AUTH_PROVIDER=local. They are created in
every environment anyway so that a deployment can switch modes without a
schema change, and so the two run modes share one migration history.

`local_credentials` is separate from `profiles` on purpose: a profile row is
routinely selected and serialized, and a password hash must never ride along
with it by accident.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_local_auth"
down_revision = "0001_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "local_credentials",
        sa.Column("profile_id", sa.Uuid(), primary_key=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        # SHA-256 hex only - a database leak must not yield usable sessions.
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_auth_tokens_token_hash", "auth_tokens", ["token_hash"])
    op.create_index("ix_auth_tokens_profile_kind", "auth_tokens", ["profile_id", "kind"])

    if op.get_bind().dialect.name == "postgresql":
        # Nothing but the backend's own connection should ever read these.
        op.execute("ALTER TABLE local_credentials ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE auth_tokens ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_auth_tokens_profile_kind", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_token_hash", table_name="auth_tokens")
    op.drop_table("auth_tokens")
    op.drop_table("local_credentials")
