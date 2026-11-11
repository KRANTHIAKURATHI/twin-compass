"""Refresh-token rotation is single-use under CONCURRENT requests, on real PostgreSQL.

The consume step is one conditional UPDATE (`... WHERE token_hash = :h AND used_at IS NULL AND revoked_at IS NULL`).
Only PostgreSQL's row locking / READ COMMITTED re-evaluation proves that exactly one of N simultaneous requests wins,
so this runs against the disposable test database only. Skipped unless ONCOTWIN_TEST_PG_URL is set.

Safety (same guards as the other PostgreSQL tests): host 127.0.0.1/localhost, database exactly `oncotwin_it`, role
exactly `oncotwin_test`; the public schema of that database is rebuilt for every test.
"""
from __future__ import annotations

import asyncio
import os
import threading

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.base import Base
from app.models.identity import AuthToken, Profile, Role, SEED_ROLES
from tests.conftest import register

PG_URL = os.environ.get("ONCOTWIN_TEST_PG_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="ONCOTWIN_TEST_PG_URL is not set")

ORIGIN = "http://localhost:5173"  # in the default CORS_ALLOWED_ORIGINS
COOKIE = "oncotwin_refresh_token"
PASSWORD = "secret123"


@pytest_asyncio.fixture()
async def db_sessionmaker():
    url = make_url(PG_URL)
    assert url.host in ("127.0.0.1", "localhost") and url.database == "oncotwin_it" and url.username == "oncotwin_test"
    engine = create_async_engine(PG_URL, poolclass=NullPool)  # a fresh connection per session: real concurrency
    async with engine.begin() as conn:
        assert (await conn.execute(text("select current_database()"))).scalar() == "oncotwin_it"
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with maker() as s:
        s.add_all([Role(id=i, name=n, description=d) for i, n, d in SEED_ROLES])
        await s.commit()
    yield maker
    await engine.dispose()


def _login(client: TestClient, email: str) -> str:
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.cookies[COOKIE]


def _refresh(client: TestClient, token: str):
    return client.post("/auth/refresh", headers={"Origin": ORIGIN, "Cookie": f"{COOKIE}={token}"})


def _race(client: TestClient, token: str, n: int):
    """n simultaneous refreshes with the SAME token, released together by a barrier."""
    results, barrier = [], threading.Barrier(n)

    def go():
        barrier.wait()
        results.append(_refresh(client, token))

    threads = [threading.Thread(target=go) for _ in range(n)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return results


def _tokens(db_sessionmaker, email: str):
    async def go():
        async with db_sessionmaker() as s:
            pid = (await s.execute(select(Profile.id).where(Profile.email == email))).scalar_one()
            return (await s.execute(select(AuthToken).where(AuthToken.profile_id == pid, AuthToken.kind == "refresh"))).scalars().all()

    return asyncio.run(go())


def test_normal_refresh_returns_200_and_rotates(client):
    register(client)
    t0 = _login(client, "doc@example.com")
    r = _refresh(client, t0)
    assert r.status_code == 200 and r.cookies[COOKIE] != t0


def test_sequential_replay_is_rejected_and_revokes_the_users_sessions(client, db_sessionmaker):
    register(client)
    t0 = _login(client, "doc@example.com")
    other_device = _login(client, "doc@example.com")
    winner = _refresh(client, t0)
    assert winner.status_code == 200
    assert _refresh(client, t0).status_code == 401  # replay
    assert all(t.revoked_at is not None for t in _tokens(db_sessionmaker, "doc@example.com"))
    for token in (winner.cookies[COOKIE], other_device):
        assert _refresh(client, token).status_code == 401


@pytest.mark.parametrize("n,rounds", [(2, 12), (8, 4)])
def test_concurrent_refresh_with_the_same_token_has_exactly_one_winner(client, db_sessionmaker, n, rounds):
    register(client)
    for _ in range(rounds):
        token = _login(client, "doc@example.com")
        results = _race(client, token, n)
        statuses = sorted(r.status_code for r in results)
        assert statuses == [200] + [401] * (n - 1), f"expected exactly 1 success and {n - 1} rejections, got {statuses}"

        winners = [r for r in results if r.status_code == 200]
        losers = [r for r in results if r.status_code == 401]
        assert COOKIE in winners[0].cookies and "accessToken" in winners[0].json()
        for loser in losers:  # a loser must not leave with anything usable
            assert COOKIE not in loser.cookies and "set-cookie" not in loser.headers
            assert "accessToken" not in loser.text


def test_concurrent_loser_is_treated_as_replay_and_no_live_session_survives(client, db_sessionmaker):
    register(client)
    token = _login(client, "doc@example.com")
    results = _race(client, token, 2)
    assert sorted(r.status_code for r in results) == [200, 401]
    winner_token = next(r for r in results if r.status_code == 200).cookies[COOKIE]

    rows = _tokens(db_sessionmaker, "doc@example.com")
    assert [t for t in rows if t.used_at is None and t.revoked_at is None] == [], "no refresh token may remain live"
    assert _refresh(client, winner_token).status_code == 401  # same replay semantics as the sequential case
    assert _refresh(client, token).status_code == 401


def test_another_users_refresh_token_is_unaffected_by_the_race(client, db_sessionmaker):
    register(client)
    register(client, email="other@example.com", name="Dr. Other")
    bystander = _login(client, "other@example.com")
    token = _login(client, "doc@example.com")
    assert sorted(r.status_code for r in _race(client, token, 2)) == [200, 401]
    assert _refresh(client, bystander).status_code == 200
    assert all(t.revoked_at is None for t in _tokens(db_sessionmaker, "other@example.com") if t.used_at is None)
