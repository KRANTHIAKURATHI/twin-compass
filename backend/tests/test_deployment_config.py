"""Deployment-facing configuration behaviour (Render + Supabase). No application logic is exercised here."""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings

SUPABASE_ENV = {
    "SUPABASE_URL": "https://example-ref.supabase.co",
    "SUPABASE_ANON_KEY": "dummy-anon",
    "SUPABASE_SERVICE_ROLE_KEY": "dummy-service",
    "SUPABASE_JWT_SECRET": "dummy-jwt-secret-dummy-jwt-secret-1234",
}


def _settings(**overrides):
    # _env_file=None: never read a developer's .env while testing configuration rules. The test environment turns the
    # Secure cookie off (plain-HTTP TestClient), so production-shaped settings must ask for it explicitly.
    overrides.setdefault("REFRESH_COOKIE_SECURE", True)
    return Settings(_env_file=None, **overrides)


# --- DATABASE_URL: Supabase hands out `postgresql://`; the async engine needs `+asyncpg` ----------------------

@pytest.mark.parametrize("given", ["postgresql://u:p@host:6543/postgres", "postgres://u:p@host:6543/postgres"])
def test_plain_postgres_urls_are_upgraded_to_the_asyncpg_driver(given):
    s = _settings(DATABASE_URL=given)
    assert s.DATABASE_URL == "postgresql+asyncpg://u:p@host:6543/postgres"
    create_async_engine(s.DATABASE_URL)  # would raise "No module named 'psycopg2'" for the plain scheme


@pytest.mark.parametrize("given", ["postgresql+asyncpg://u:p@h/db", "sqlite+aiosqlite:///./x.db"])
def test_explicit_driver_urls_are_left_alone(given):
    assert _settings(DATABASE_URL=given).DATABASE_URL == given


def test_upgraded_url_keeps_credentials_host_port_and_database():
    s = _settings(DATABASE_URL="postgresql://user.ref:dummy-pass@db.example.test:6543/postgres")
    assert s.DATABASE_URL == "postgresql+asyncpg://user.ref:dummy-pass@db.example.test:6543/postgres"


# --- production rules that a bad Render env must trip loudly -------------------------------------------------

def test_production_supabase_requires_a_postgres_database_and_the_supabase_keys():
    ok = _settings(ENVIRONMENT="prod", AUTH_PROVIDER="supabase", DATABASE_URL="postgresql://u:p@h:6543/db", **SUPABASE_ENV)
    assert ok.DATABASE_URL.startswith("postgresql+asyncpg://")
    with pytest.raises(ValidationError):
        _settings(ENVIRONMENT="prod", AUTH_PROVIDER="supabase", DATABASE_URL="sqlite+aiosqlite:///./x.db", **SUPABASE_ENV)
    with pytest.raises(ValidationError):
        _settings(ENVIRONMENT="prod", AUTH_PROVIDER="supabase", DATABASE_URL="postgresql://u:p@h/db")


def test_production_refuses_an_insecure_refresh_cookie_and_wildcard_cors():
    base = dict(ENVIRONMENT="prod", AUTH_PROVIDER="supabase", DATABASE_URL="postgresql://u:p@h/db", **SUPABASE_ENV)
    with pytest.raises(ValidationError):
        _settings(REFRESH_COOKIE_SECURE=False, **base)
    with pytest.raises(ValidationError):
        _settings(CORS_ALLOWED_ORIGINS=["*"], **base)


def test_environment_name_must_be_one_of_the_known_values():
    with pytest.raises(ValidationError):
        _settings(ENVIRONMENT="production")  # the setting is `prod`; `development`/`production` are rejected


def test_cors_allowed_origins_from_the_environment_must_be_a_json_list(monkeypatch):
    """Documents the Render env format: CORS_ALLOWED_ORIGINS='["https://app.example.com"]' (not comma-separated)."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://app.example.com","https://www.example.com"]')
    assert _settings().CORS_ALLOWED_ORIGINS == ["https://app.example.com", "https://www.example.com"]
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example.com,https://www.example.com")
    with pytest.raises(SettingsError):
        _settings()


# --- the public readiness probe must not leak infrastructure details -------------------------------------------

def test_readiness_does_not_echo_database_errors(client, monkeypatch):
    import app.db.session as session_module

    secret = 'password authentication failed for user "postgres.abcdefghijklmnop" at db.internal.example:6543'

    def boom():
        raise RuntimeError(secret)

    monkeypatch.setattr(session_module, "get_sessionmaker", boom)
    r = client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded" and body["database_ok"] is False
    assert "detail" not in body
    assert "postgres.abcdefghijklmnop" not in r.text and "db.internal.example" not in r.text


def test_readiness_still_reports_a_healthy_database(client):
    body = client.get("/health/ready").json()
    assert body["status"] == "ok" and body["database_ok"] is True and "detail" not in body
