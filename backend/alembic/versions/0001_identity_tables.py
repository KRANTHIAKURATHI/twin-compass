"""Module 1: identity tables (roles, profiles, user_roles)

Revision ID: 0001_identity
Revises:
Create Date: Module 1 - Authentication & Authorization

Implements Database Architecture Blueprint Sections 3.1-3.3, extended with a
fourth seed role (`patient`) per docs/module-1-auth-summary.md.

Portability
-----------
The original version of this migration was Supabase-only: it declared a hard
foreign key to `auth.users.id` and created RLS policies calling `auth.uid()`.
Both exist only inside a Supabase project, so the migration could not run
against plain PostgreSQL or SQLite - which made the file-backed run mode
impossible.

It is now dialect- and platform-aware:
  * the `auth.users` FK is added only when that table actually exists;
  * RLS is applied only on PostgreSQL, and the `auth.uid()` policies only
    when the Supabase `auth` schema is present;
  * `sa.Uuid` renders natively on PostgreSQL and as CHAR(32) elsewhere.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_identity"
down_revision = None
branch_labels = None
depends_on = None


def _dialect() -> str:
    return op.get_bind().dialect.name


def _has_supabase_auth() -> bool:
    """True only inside a Supabase project (or any DB with an auth.users table)."""
    if _dialect() != "postgresql":
        return False
    return bool(
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'auth' AND table_name = 'users'"
            )
        )
        .scalar()
    )


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("name", sa.String(length=32), nullable=False, unique=True),
        sa.Column("description", sa.String(length=255), nullable=True),
    )

    op.create_table(
        "profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("hospital", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("license_number", sa.String(length=100), nullable=True),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_profiles_email", "profiles", ["email"])

    # Supabase only: tie the profile to the auth user it extends.
    if _has_supabase_auth():
        op.create_foreign_key(
            "fk_profiles_id_auth_users",
            "profiles",
            "users",
            ["id"],
            ["id"],
            source_schema=None,
            referent_schema="auth",
            ondelete="CASCADE",
        )

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.SmallInteger(), nullable=False),
        sa.Column("granted_by", sa.Uuid(), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(["granted_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("profile_id", "role_id", name="uq_user_roles_profile_role"),
    )
    op.create_index("ix_user_roles_profile_id", "user_roles", ["profile_id"])

    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("id", sa.SmallInteger),
            sa.column("name", sa.String),
            sa.column("description", sa.String),
        ),
        [
            {"id": 1, "name": "doctor", "description": "Clinician with full patient/twin/prediction access."},
            {"id": 2, "name": "admin", "description": "Platform/hospital administrator."},
            {"id": 3, "name": "researcher", "description": "Read-only, de-identified aggregate access."},
            {"id": 4, "name": "patient", "description": "Patient portal user - own-record access only."},
        ],
    )

    # --- Row Level Security (PostgreSQL only) -----------------------------
    # Defence in depth beneath the FastAPI-layer RBAC. Backend writes use a
    # service-role connection that bypasses RLS by design; these policies
    # protect any future direct-client path. SQLite has no equivalent, and
    # the auth.uid() policies need Supabase's auth schema.
    if _dialect() == "postgresql":
        op.execute("ALTER TABLE profiles ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE roles ENABLE ROW LEVEL SECURITY")
        op.execute("CREATE POLICY roles_read_all ON roles FOR SELECT USING (true)")
        if _has_supabase_auth():
            op.execute("CREATE POLICY profiles_self_select ON profiles FOR SELECT USING (auth.uid() = id)")
            op.execute("CREATE POLICY profiles_self_update ON profiles FOR UPDATE USING (auth.uid() = id)")
            op.execute(
                "CREATE POLICY user_roles_self_select ON user_roles FOR SELECT USING (auth.uid() = profile_id)"
            )
        # Without Supabase there is no auth.uid(); RLS stays enabled with no
        # permissive policy, i.e. deny-all to non-superusers, which is the
        # safe default for a table only the backend should reach.


def downgrade() -> None:
    if _dialect() == "postgresql":
        for stmt in (
            "DROP POLICY IF EXISTS roles_read_all ON roles",
            "DROP POLICY IF EXISTS user_roles_self_select ON user_roles",
            "DROP POLICY IF EXISTS profiles_self_update ON profiles",
            "DROP POLICY IF EXISTS profiles_self_select ON profiles",
        ):
            op.execute(stmt)
    op.drop_index("ix_user_roles_profile_id", table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index("ix_profiles_email", table_name="profiles")
    op.drop_table("profiles")
    op.drop_table("roles")
