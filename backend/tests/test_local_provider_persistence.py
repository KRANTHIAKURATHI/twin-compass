"""
H2: failed-login lockout and refresh-replay revocation must survive the request's rollback.

The provider raises an AuthenticationError after mutating security state; the session dependency rolls
back on any exception. These tests read the state through a brand-new session (never the request's
session), so they cannot pass by sharing a transaction.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.auth.providers.local_provider import MAX_FAILED_ATTEMPTS
from app.models.identity import AuthToken, LocalCredential, Profile
from tests.conftest import login, register


def _fresh(db_sessionmaker, email: str):
    """(failed_attempts, locked_until, [revoked_at per refresh token]) read in a new session."""

    async def _go():
        async with db_sessionmaker() as s:
            pid = (await s.execute(select(Profile.id).where(Profile.email == email))).scalar_one()
            cred = (await s.execute(select(LocalCredential).where(LocalCredential.profile_id == pid))).scalar_one()
            toks = (await s.execute(select(AuthToken).where(AuthToken.profile_id == pid, AuthToken.kind == "refresh"))).scalars().all()
            return cred.failed_attempts, cred.locked_until, [t.revoked_at for t in toks]

    return asyncio.run(_go())


def _bad(client, email, n):
    for _ in range(n):
        assert client.post("/auth/login", json={"email": email, "password": "wrong-password-1"}).status_code == 401


def test_failed_attempts_persist_across_requests(client, db_sessionmaker):
    register(client)
    _bad(client, "doc@example.com", 3)
    attempts, locked, _ = _fresh(db_sessionmaker, "doc@example.com")
    assert attempts == 3 and locked is None


def test_lockout_persists_and_blocks_correct_password(client, db_sessionmaker):
    register(client)
    _bad(client, "doc@example.com", MAX_FAILED_ATTEMPTS)
    attempts, locked, _ = _fresh(db_sessionmaker, "doc@example.com")
    assert attempts == MAX_FAILED_ATTEMPTS and locked is not None

    blocked = client.post("/auth/login", json={"email": "doc@example.com", "password": "secret123"})
    assert blocked.status_code == 401
    assert "Too many failed" in blocked.text


def test_successful_login_resets_counter(client, db_sessionmaker):
    register(client)
    _bad(client, "doc@example.com", 4)
    assert _fresh(db_sessionmaker, "doc@example.com")[0] == 4
    assert login(client).status_code == 200
    attempts, locked, _ = _fresh(db_sessionmaker, "doc@example.com")
    assert attempts == 0 and locked is None


def test_expired_lock_allows_login_and_clears_state(client, db_sessionmaker):
    register(client)
    _bad(client, "doc@example.com", MAX_FAILED_ATTEMPTS)

    async def _expire():
        from datetime import datetime, timedelta, timezone

        async with db_sessionmaker() as s:
            pid = (await s.execute(select(Profile.id).where(Profile.email == "doc@example.com"))).scalar_one()
            cred = (await s.execute(select(LocalCredential).where(LocalCredential.profile_id == pid))).scalar_one()
            cred.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
            await s.commit()

    asyncio.run(_expire())
    assert login(client).status_code == 200
    attempts, locked, _ = _fresh(db_sessionmaker, "doc@example.com")
    assert attempts == 0 and locked is None


def test_replay_revocation_persists_and_stays_rejected(client, db_sessionmaker, settings):
    name = settings.REFRESH_COOKIE_NAME
    register(client)
    stolen = login(client).cookies[name]
    rotated = client.post("/auth/refresh").cookies[name]  # rotates `stolen`

    client.cookies.clear()
    client.cookies.set(name, stolen)
    assert client.post("/auth/refresh").status_code == 401  # replay

    revoked = _fresh(db_sessionmaker, "doc@example.com")[2]
    assert revoked and all(r is not None for r in revoked), "family revocation must be committed"

    # The legitimately rotated token is part of the revoked family, and a second replay stays rejected.
    client.cookies.clear()
    client.cookies.set(name, rotated)
    assert client.post("/auth/refresh").status_code == 401
    client.cookies.clear()
    client.cookies.set(name, stolen)
    assert client.post("/auth/refresh").status_code == 401


def test_replay_does_not_revoke_another_users_session(client, db_sessionmaker, settings):
    name = settings.REFRESH_COOKIE_NAME
    register(client, email="victim@example.com")
    register(client, email="other@example.com")
    other = login(client, email="other@example.com").cookies[name]
    stolen = login(client, email="victim@example.com").cookies[name]
    client.cookies.clear()
    client.cookies.set(name, stolen)
    assert client.post("/auth/refresh").status_code == 200  # rotate
    client.cookies.clear()
    client.cookies.set(name, stolen)
    assert client.post("/auth/refresh").status_code == 401  # replay

    assert all(r is None for r in _fresh(db_sessionmaker, "other@example.com")[2])
    client.cookies.clear()
    client.cookies.set(name, other)
    assert client.post("/auth/refresh").status_code == 200
