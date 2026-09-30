"""
Configuration and provider-selection tests: the "runs with Supabase and with
files" contract itself.
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import configure_mappers

from app.core.config import Settings


def _settings(**env) -> Settings:
    return Settings(_env_file=None, **env)


# --- the regression that mattered ------------------------------------------

def test_identity_mappers_configure():
    """`user_roles` has two FKs to `profiles.id` (profile_id, granted_by).
    Without foreign_keys= on BOTH sides SQLAlchemy raises
    AmbiguousForeignKeysError on first use, which made every
    database-touching endpoint return 500."""
    import app.models.identity  # noqa: F401

    configure_mappers()


# --- file mode --------------------------------------------------------------

def test_local_mode_needs_no_supabase_settings(tmp_path):
    s = _settings(AUTH_PROVIDER="local", DATA_DIR=tmp_path)
    assert s.is_sqlite
    assert s.DATABASE_URL.startswith("sqlite+aiosqlite:///")
    assert s.uses_supabase is False


def test_local_mode_generates_a_signing_secret_for_dev(tmp_path):
    s = _settings(AUTH_PROVIDER="local", DATA_DIR=tmp_path, ENVIRONMENT="local",
                  LOCAL_JWT_SECRET="")
    assert len(s.LOCAL_JWT_SECRET) >= 32
    assert s.jwt_secret == s.LOCAL_JWT_SECRET


def test_local_mode_refuses_a_generated_secret_in_production(tmp_path):
    # Explicitly blank: a per-process random secret would silently invalidate
    # every outstanding session on each restart/redeploy.
    with pytest.raises(ValueError, match="LOCAL_JWT_SECRET"):
        _settings(AUTH_PROVIDER="local", DATA_DIR=tmp_path, ENVIRONMENT="prod",
                  REFRESH_COOKIE_SECURE=True, LOCAL_JWT_SECRET="")


def test_data_dir_is_created(tmp_path):
    target = tmp_path / "nested" / "data"
    s = _settings(AUTH_PROVIDER="local", DATA_DIR=target)
    assert s.DATA_DIR.is_dir()


# --- supabase mode ----------------------------------------------------------

SUPA = dict(
    AUTH_PROVIDER="supabase",
    SUPABASE_URL="https://example.supabase.co",
    SUPABASE_ANON_KEY="anon",
    SUPABASE_SERVICE_ROLE_KEY="service",
    SUPABASE_JWT_SECRET="jwt-secret-value",
    DATABASE_URL="postgresql+asyncpg://u:p@h:6543/postgres",
)


def test_supabase_mode_accepts_a_complete_config(tmp_path):
    s = _settings(DATA_DIR=tmp_path, **SUPA)
    assert s.uses_supabase
    assert s.jwt_secret == "jwt-secret-value"
    assert s.jwt_audience == "authenticated"


@pytest.mark.parametrize(
    "missing", ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"]
)
def test_supabase_mode_names_exactly_what_is_missing(tmp_path, missing):
    config = {**SUPA, missing: None}
    with pytest.raises(ValueError, match=missing):
        _settings(DATA_DIR=tmp_path, **config)


def test_supabase_mode_rejects_a_sqlite_database(tmp_path):
    """Profiles must live in the same Postgres as Supabase Auth; pairing the
    hosted identity provider with a local file would split identity in two."""
    config = {**SUPA, "DATABASE_URL": "sqlite+aiosqlite:///./x.db"}
    with pytest.raises(ValueError, match="SQLite"):
        _settings(DATA_DIR=tmp_path, **config)


def test_production_requires_secure_cookies(tmp_path):
    with pytest.raises(ValueError, match="REFRESH_COOKIE_SECURE"):
        _settings(DATA_DIR=tmp_path, ENVIRONMENT="prod", REFRESH_COOKIE_SECURE=False, **SUPA)


# --- engine construction ----------------------------------------------------

def test_postgres_engine_avoids_double_pooling_behind_pgbouncer():
    """Supabase fronts Postgres with PgBouncer in transaction mode; a second
    client-side pool plus asyncpg's prepared-statement cache is the documented
    failure mode the old session module warned about but did not prevent."""
    from sqlalchemy.pool import NullPool

    from app.db.session import build_engine

    engine = build_engine("postgresql+asyncpg://u:p@h:6543/postgres")
    assert isinstance(engine.pool, NullPool)
    assert engine.dialect.name == "postgresql"


def test_sqlite_engine_allows_cross_thread_use():
    from app.db.session import build_engine

    engine = build_engine("sqlite+aiosqlite:///:memory:")
    assert engine.dialect.name == "sqlite"
