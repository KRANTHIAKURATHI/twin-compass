"""
Tests for the active /notifications routes (backend/app/api/v1/routers/notifications.py).

The router uses plain, portable SQL against the existing `notifications`
table, so unlike the Postgres-only document/twin SQL it can be exercised
against the per-test SQLite database. The table is created here with the
live column set (id, user_id, audience_role, title, body, time, unread, type)
purely as a test fixture - the real table lives in Supabase Postgres.
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from tests.conftest import login, register

ROUTES = [
    ("POST", "/notifications/{notification_id}/read"),
    ("POST", "/notifications/read-all"),
    ("GET", "/notifications"),
]


def _headers(client, email: str, role: str = "doctor") -> dict[str, str]:
    register(client, email=email, role=role)
    token = login(client, email=email).json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def _user_id(client, headers) -> str:
    return client.get("/auth/me", headers=headers).json()["id"]


@pytest.fixture()
def seed(db_sessionmaker):
    """Creates the notifications table and returns an inserter."""

    async def _setup():
        async with db_sessionmaker() as s:
            await s.execute(
                text(
                    "CREATE TABLE notifications (id TEXT PRIMARY KEY, user_id TEXT, "
                    "audience_role TEXT, title TEXT, body TEXT, time TEXT, "
                    "unread BOOLEAN DEFAULT 1, type TEXT)"
                )
            )
            await s.commit()

    asyncio.run(_setup())

    def _insert(id_: str, *, user_id=None, audience_role=None, time="2026-01-01T00:00:00Z", unread=True):
        async def _go():
            async with db_sessionmaker() as s:
                await s.execute(
                    text(
                        "INSERT INTO notifications (id, user_id, audience_role, title, body, time, unread) "
                        "VALUES (:id, :u, :r, :t, 'body', :time, :unread)"
                    ),
                    {"id": id_, "u": user_id, "r": audience_role, "t": f"title-{id_}", "time": time, "unread": unread},
                )
                await s.commit()

        asyncio.run(_go())

    def _is_unread(id_: str) -> bool:
        async def _go():
            async with db_sessionmaker() as s:
                row = (await s.execute(text("SELECT unread FROM notifications WHERE id = :id"), {"id": id_})).first()
                return bool(row[0])

        return asyncio.run(_go())

    _insert.is_unread = _is_unread  # type: ignore[attr-defined]
    return _insert


def test_every_frontend_notification_route_is_mounted(client):
    mounted = {(m, route.path) for route in client.app.routes for m in getattr(route, "methods", set())}
    for method, path in ROUTES:
        assert (method, path) in mounted, f"{method} {path} is missing"


@pytest.mark.parametrize("method,path", [(m, p.format(notification_id="n-1")) for m, p in ROUTES])
def test_notification_routes_require_authentication(client, method, path):
    r = getattr(client, method.lower())(path)
    assert r.status_code == 401


def test_list_returns_only_own_and_role_broadcast(client, seed):
    headers = _headers(client, "n-doc@example.com")
    other = _headers(client, "n-other@example.com")
    me, them = _user_id(client, headers), _user_id(client, other)
    seed("mine", user_id=me, time="2026-01-02T00:00:00Z")
    seed("theirs", user_id=them)
    seed("broadcast", audience_role="doctor", time="2026-01-03T00:00:00Z")
    seed("other-role", audience_role="admin")

    r = client.get("/notifications", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert [n["id"] for n in body] == ["broadcast", "mine"]  # newest first
    assert set(body[0]) == {"id", "title", "body", "time", "unread", "type"}
    assert body[0]["unread"] is True


def test_list_is_empty_when_there_are_no_notifications(client, seed):
    headers = _headers(client, "n-empty@example.com")
    r = client.get("/notifications", headers=headers)
    assert r.status_code == 200 and r.json() == []


def test_owner_can_mark_own_notification_read(client, seed):
    headers = _headers(client, "n-self@example.com")
    seed("mine", user_id=_user_id(client, headers))
    r = client.post("/notifications/mine/read", headers=headers)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert seed.is_unread("mine") is False


def test_user_can_mark_role_broadcast_read(client, seed):
    headers = _headers(client, "n-role@example.com")
    seed("bcast", audience_role="doctor")
    assert client.post("/notifications/bcast/read", headers=headers).status_code == 200
    assert seed.is_unread("bcast") is False


def test_user_cannot_mark_another_users_notification_read(client, seed):
    owner = _headers(client, "n-owner@example.com")
    intruder = _headers(client, "n-intruder@example.com")
    seed("private", user_id=_user_id(client, owner))
    r = client.post("/notifications/private/read", headers=intruder)
    assert r.status_code == 403
    assert seed.is_unread("private") is True


def test_mark_read_unknown_notification_is_404(client, seed):
    headers = _headers(client, "n-404@example.com")
    assert client.post("/notifications/nope/read", headers=headers).status_code == 404


def test_read_all_only_touches_callers_notifications(client, seed):
    headers = _headers(client, "n-all@example.com")
    other = _headers(client, "n-all-other@example.com")
    seed("a", user_id=_user_id(client, headers))
    seed("b", audience_role="doctor")
    seed("c", user_id=_user_id(client, other))
    seed("d", audience_role="admin")

    assert client.post("/notifications/read-all", headers=headers).status_code == 200
    assert seed.is_unread("a") is False and seed.is_unread("b") is False
    assert seed.is_unread("c") is True and seed.is_unread("d") is True
