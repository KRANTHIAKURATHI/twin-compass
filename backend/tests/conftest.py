"""
Shared test fixtures.

The tests are in two tiers:

  * Pure unit tests (test_security.py, test_passwords.py, test_rbac.py) -
    no I/O, no environment beyond the stub below.

  * Integration tests (test_auth_flow.py, test_auth_endpoints.py) - the REAL
    AuthService, the REAL repository and the REAL local provider, against a
    real (temporary, file-backed) SQLite database, driven through FastAPI's
    TestClient.

That second tier is the important change. The previous suite overrode both
`get_auth_service` and `get_current_user` with fakes, so no test ever built
the real object graph. A mapper-configuration bug that made every
database-touching endpoint return 500 sat behind 27 green tests. Nothing here
is allowed to stub the service layer any more.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Settings are validated at import time, so test env vars must be set before
# any app module is imported.
_TMP = Path(tempfile.mkdtemp(prefix="oncotwin-tests-"))
os.environ.setdefault("AUTH_PROVIDER", "local")
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("DATA_DIR", str(_TMP))
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TMP / 'test.db'}")
os.environ.setdefault("LOCAL_JWT_SECRET", "test-jwt-secret-at-least-32-characters-long")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-at-least-32-characters-long")
os.environ.setdefault("REFRESH_COOKIE_SECURE", "false")
# Off by default so the suite does not trip the public-endpoint budget; the
# rate-limit test turns it back on explicitly.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_LEVEL", "CRITICAL")

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.db.session import build_engine, get_db_session
from app.main import app
from app.models.base import Base
from app.models.identity import SEED_ROLES, Role

TEST_JWT_SECRET = os.environ["LOCAL_JWT_SECRET"]


@pytest_asyncio.fixture()
async def db_sessionmaker(tmp_path):
    """A fresh SQLite database per test - no cross-test bleed."""
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'case.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with maker() as session:
        session.add_all([Role(id=i, name=n, description=d) for i, n, d in SEED_ROLES])
        await session.commit()
    yield maker
    await engine.dispose()


@pytest.fixture()
def client(db_sessionmaker):
    """TestClient wired to the per-test database.

    Only the DB session is overridden. The provider, repository and service
    are the real ones, resolved through the real dependency graph.
    """

    async def _override():
        async with db_sessionmaker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def settings():
    return get_settings()


def register(client: TestClient, **overrides) -> dict:
    payload = {
        "email": "doc@example.com",
        "password": "secret123",
        "name": "Dr. Test",
        "role": "doctor",
        **overrides,
    }
    return client.post("/auth/register", json=payload)


def login(client: TestClient, email="doc@example.com", password="secret123"):
    return client.post("/auth/login", json={"email": email, "password": password})
