"""
API contract tests: error-envelope shape, rate limiting, CORS, and the exact
route paths the frontend registry expects.

Deliberately NOT stubbing AuthService. The previous version of this file
replaced the whole service and `get_current_user` with fakes, which is how a
mapper bug that broke every database-backed endpoint stayed invisible behind
a green suite. Behaviour lives in test_auth_flow.py; this file checks the
envelope and the wiring around it.
"""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from tests.conftest import login, register

# Every path in the frontend's src/services/endpoints.ts auth + users block.
FRONTEND_AUTH_ROUTES = [
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
    ("POST", "/auth/logout"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/forgot-password"),
    ("POST", "/auth/reset-password"),
    ("GET", "/auth/me"),
    ("PATCH", "/users/profile"),
]


def test_every_frontend_route_is_mounted_at_its_bare_path(client):
    mounted = {(method, route.path) for route in client.app.routes
               for method in getattr(route, "methods", set())}
    for method, path in FRONTEND_AUTH_ROUTES:
        assert (method, path) in mounted, f"{method} {path} is missing"


@pytest.mark.parametrize(
    "method,path,payload,expected",
    [
        ("post", "/auth/login", {"email": "x@y.com", "password": "nope12345"}, 401),
        ("post", "/auth/register", {"email": "bad", "password": "secret123", "name": "N"}, 422),
        ("get", "/auth/me", None, 401),
    ],
)
def test_errors_use_the_standard_envelope(client, method, path, payload, expected):
    r = getattr(client, method)(path, **({"json": payload} if payload else {}))
    assert r.status_code == expected
    envelope = r.json()["error"]
    # The shape src/services/api-client.ts parses into ApiError.
    assert set(envelope) == {"code", "message", "field", "request_id"}
    assert isinstance(envelope["code"], str) and envelope["code"]
    assert isinstance(envelope["message"], str) and envelope["message"]


def test_validation_error_names_the_offending_field(client):
    r = register(client, email="not-an-email")
    assert r.status_code == 422
    assert r.json()["error"]["field"] == "email"


def test_every_response_carries_a_request_id_header(client):
    r = client.get("/health")
    assert r.headers.get("X-Request-ID")


def test_request_id_is_echoed_when_supplied(client):
    r = client.get("/health", headers={"X-Request-ID": "trace-me-123"})
    assert r.headers["X-Request-ID"] == "trace-me-123"


def test_cors_allows_the_configured_origin_with_credentials(client, settings):
    origin = settings.CORS_ALLOWED_ORIGINS[0]
    r = client.options(
        "/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origin
    # Required for the httpOnly refresh cookie to survive cross-origin.
    assert r.headers["access-control-allow-credentials"] == "true"


def test_login_response_never_contains_the_refresh_token(client):
    register(client)
    r = login(client)
    cookie = r.cookies["oncotwin_refresh_token"]
    assert cookie not in r.text


def test_rate_limiting_returns_the_envelope_not_a_bare_string(monkeypatch, tmp_path):
    """slowapi's default handler emits {"error": "<string>"}, which the
    frontend cannot parse into ApiError. Registering it after our own handler
    silently replaced the envelope; this pins the fix."""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("AUTH_RATE_LIMIT", "2/minute")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'rl.db'}")

    import app.core.config as config_module

    config_module.get_settings.cache_clear()
    for name in ("app.api.v1.routers.auth", "app.api.v1.router", "app.main"):
        importlib.reload(importlib.import_module(name))
    limited_app = importlib.import_module("app.main").app

    try:
        with TestClient(limited_app) as c:
            statuses = [
                c.post("/auth/forgot-password", json={"email": "a@b.com"}).status_code
                for _ in range(4)
            ]
            assert 429 in statuses
            body = c.post("/auth/forgot-password", json={"email": "a@b.com"}).json()
            assert body["error"]["code"] == "RATE_LIMITED"
            assert isinstance(body["error"], dict)
            assert body["error"]["request_id"]
    finally:
        monkeypatch.undo()
        config_module.get_settings.cache_clear()
        for name in ("app.api.v1.routers.auth", "app.api.v1.router", "app.main"):
            importlib.reload(importlib.import_module(name))
