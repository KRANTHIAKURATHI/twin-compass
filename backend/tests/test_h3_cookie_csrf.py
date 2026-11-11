"""H3: same-origin `/api` proxy topology - refresh-cookie attributes, origin (CSRF) defence, CORS, multi-tab race.

The Vercel rewrite itself is checked in the frontend guard test (src/services/api-proxy.guard.test.mjs).
Here: what the backend must guarantee behind that proxy.
"""
from __future__ import annotations

from contextlib import contextmanager
from http.cookies import SimpleCookie

import pytest
from pydantic import ValidationError

from app.api.v1.routers import auth as auth_router
from app.core.config import Settings, get_settings
from tests.conftest import login, register
from tests.test_local_provider_persistence import _fresh

FRONTEND = "http://localhost:5173"  # in the default CORS_ALLOWED_ORIGINS
EVIL = "https://evil.example"


@contextmanager
def _patched(obj, **values):
    old = {k: getattr(obj, k) for k in values}
    for k, v in values.items():
        object.__setattr__(obj, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            object.__setattr__(obj, k, v)


def _morsel(response, name):
    jar = SimpleCookie()
    jar.load(response.headers["set-cookie"])
    return jar[name]


def _attrs(m):
    """Everything about a cookie except its value/expiry - what a deletion must reproduce."""
    return {
        "path": m["path"], "domain": m["domain"], "secure": bool(m["secure"]),
        "httponly": bool(m["httponly"]), "samesite": m["samesite"].lower(),
    }


def _session(client, settings):
    register(client)
    assert login(client).status_code == 200
    return client.cookies[settings.REFRESH_COOKIE_NAME]


# --- cookie attributes ---------------------------------------------------------------------------

def test_refresh_cookie_attributes_in_production_shape(client, settings):
    with _patched(auth_router.settings, REFRESH_COOKIE_SECURE=True):
        register(client)
        r = client.post("/auth/login", json={"email": "doc@example.com", "password": "secret123"})
    m = _morsel(r, settings.REFRESH_COOKIE_NAME)
    assert _attrs(m) == {"path": "/", "domain": "", "secure": True, "httponly": True, "samesite": "lax"}
    assert int(m["max-age"]) == settings.REFRESH_COOKIE_MAX_AGE_SECONDS


def test_default_samesite_is_lax_and_none_is_not_configured():
    assert Settings.model_fields["REFRESH_COOKIE_SAMESITE"].default == "lax"
    assert get_settings().REFRESH_COOKIE_SAMESITE != "none"


@pytest.mark.parametrize("secure", [True, False])
def test_clear_cookie_attributes_match_set_cookie(client, settings, secure):
    with _patched(auth_router.settings, REFRESH_COOKIE_SECURE=secure):
        register(client)
        set_r = client.post("/auth/login", json={"email": "doc@example.com", "password": "secret123"})
        out = client.post("/auth/logout", headers={"Origin": FRONTEND})
    assert out.status_code == 200
    cleared = _morsel(out, settings.REFRESH_COOKIE_NAME)
    assert _attrs(cleared) == _attrs(_morsel(set_r, settings.REFRESH_COOKIE_NAME))
    assert cleared.value == "" and int(cleared["max-age"]) == 0


def test_refresh_cookie_is_rotated_with_the_same_attributes(client, settings):
    with _patched(auth_router.settings, REFRESH_COOKIE_SECURE=True):
        register(client)
        first = client.post("/auth/login", json={"email": "doc@example.com", "password": "secret123"})
        client.cookies.clear()
        client.cookies.set(settings.REFRESH_COOKIE_NAME, _morsel(first, settings.REFRESH_COOKIE_NAME).value)
        again = client.post("/auth/refresh", headers={"Origin": FRONTEND})
    assert again.status_code == 200
    assert _attrs(_morsel(again, settings.REFRESH_COOKIE_NAME)) == _attrs(_morsel(first, settings.REFRESH_COOKIE_NAME))


# --- CSRF / origin defence -----------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/auth/refresh", "/auth/logout"])
def test_listed_frontend_origin_is_accepted(client, settings, path):
    _session(client, settings)
    assert client.post(path, headers={"Origin": FRONTEND}).status_code == 200


@pytest.mark.parametrize("path", ["/auth/refresh", "/auth/logout"])
@pytest.mark.parametrize("origin", [EVIL, "null", "http://localhost:5173.evil.example", "http://localhost:9999", "*"])
def test_unexpected_origin_is_rejected_and_has_no_side_effect(client, settings, path, origin):
    cookie = _session(client, settings)
    r = client.post(path, headers={"Origin": origin})
    assert r.status_code == 403 and r.json()["error"]["code"] == "AUTHORIZATION_ERROR"
    assert "set-cookie" not in r.headers, "a rejected request must not rotate or clear the cookie"
    # The session is untouched: the same cookie still refreshes from the real frontend.
    ok = client.post("/auth/refresh", headers={"Origin": FRONTEND})
    assert ok.status_code == 200 and client.cookies[settings.REFRESH_COOKIE_NAME] != cookie


@pytest.mark.parametrize("path", ["/auth/refresh", "/auth/logout"])
@pytest.mark.parametrize("site", ["cross-site", "same-site"])
def test_missing_origin_with_cross_site_fetch_metadata_is_rejected(client, settings, path, site):
    _session(client, settings)
    assert client.post(path, headers={"Sec-Fetch-Site": site}).status_code == 403


@pytest.mark.parametrize("site", ["same-origin", "none"])
def test_missing_origin_with_same_origin_fetch_metadata_is_accepted(client, settings, site):
    _session(client, settings)
    assert client.post("/auth/refresh", headers={"Sec-Fetch-Site": site}).status_code == 200


def test_no_origin_and_no_fetch_metadata_is_a_non_browser_client_and_is_accepted(client, settings):
    """curl / server-to-server / the test client. A cross-site attack needs a victim's browser, which always sends one."""
    _session(client, settings)
    assert client.post("/auth/refresh").status_code == 200
    assert client.post("/auth/logout").status_code == 200


def test_origin_wins_over_fetch_metadata(client, settings):
    """Direct cross-origin dev setup (localhost:5173 -> :8000) is Sec-Fetch-Site: same-site but its Origin is listed."""
    _session(client, settings)
    r = client.post("/auth/refresh", headers={"Origin": FRONTEND, "Sec-Fetch-Site": "same-site"})
    assert r.status_code == 200


def test_wildcard_in_the_allow_list_never_matches_an_origin(client, settings):
    _session(client, settings)
    with _patched(get_settings(), CORS_ALLOWED_ORIGINS=["*"]):
        assert client.post("/auth/refresh", headers={"Origin": EVIL}).status_code == 403


def test_login_is_not_gated_by_the_origin_check(client):
    register(client)
    r = client.post("/auth/login", json={"email": "doc@example.com", "password": "secret123"},
                    headers={"Origin": EVIL})
    assert r.status_code == 200  # login carries no ambient cookie authority; out of H3 scope


# --- CORS ----------------------------------------------------------------------------------------

def _preflight(client, origin):
    return client.options("/auth/refresh", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})


def test_cors_unlisted_origin_gets_no_allow_origin(client):
    r = _preflight(client, EVIL)
    assert "access-control-allow-origin" not in r.headers
    assert r.status_code == 400


def test_cors_listed_origin_is_echoed_exactly_with_credentials(client):
    r = _preflight(client, FRONTEND)
    assert r.headers["access-control-allow-origin"] == FRONTEND
    assert r.headers["access-control-allow-credentials"] == "true"


def test_cors_never_answers_wildcard(client, settings):
    _session(client, settings)
    for origin in (EVIL, FRONTEND, "null"):
        r = client.post("/auth/refresh", headers={"Origin": origin})
        assert r.headers.get("access-control-allow-origin") != "*"


def test_settings_reject_a_wildcard_cors_origin():
    with pytest.raises(ValidationError):
        Settings(CORS_ALLOWED_ORIGINS=["*"])


# --- proxy contract: the backend has no /api prefix ----------------------------------------------

@pytest.mark.parametrize("method,path", [("post", "/api/auth/login"), ("post", "/api/auth/refresh"),
                                         ("post", "/api/auth/logout"), ("get", "/api/patients")])
def test_backend_does_not_serve_an_api_prefix(client, method, path):
    """The Vercel rewrite strips `/api`; a duplicate prefixed route on the backend would be a second, unreviewed surface."""
    assert getattr(client, method)(path).status_code == 404


def test_unprefixed_auth_routes_exist(client):
    assert client.post("/auth/refresh").status_code == 401  # reachable; just no session
    assert client.post("/auth/login", json={"email": "x@example.com", "password": "nope-nope1"}).status_code == 401


# --- multi-tab refresh race (documents current behaviour; rotation is deliberately NOT redesigned) -

def test_sequential_replay_of_a_rotated_token_revokes_every_session_of_the_user(client, settings, db_sessionmaker):
    t0 = _session(client, settings)
    client.cookies.clear()
    assert login(client).status_code == 200               # a second session (e.g. another device), same user
    t_other = client.cookies[settings.REFRESH_COOKIE_NAME]

    client.cookies.clear(); client.cookies.set(settings.REFRESH_COOKIE_NAME, t0)
    tab1 = client.post("/auth/refresh", headers={"Origin": FRONTEND})                       # "tab 1" wins
    assert tab1.status_code == 200
    t1 = tab1.cookies[settings.REFRESH_COOKIE_NAME]

    client.cookies.clear(); client.cookies.set(settings.REFRESH_COOKIE_NAME, t0)           # "tab 2" still holds the old cookie
    assert client.post("/auth/refresh", headers={"Origin": FRONTEND}).status_code == 401

    _, _, revoked = _fresh(db_sessionmaker, "doc@example.com")
    assert revoked and all(r is not None for r in revoked), "replay revokes ALL of the user's refresh tokens"
    for token in (t1, t_other):                            # tab 1's fresh token and the other device are both dead
        client.cookies.clear(); client.cookies.set(settings.REFRESH_COOKIE_NAME, token)
        assert client.post("/auth/refresh", headers={"Origin": FRONTEND}).status_code == 401


def test_concurrent_refresh_with_one_token_lets_at_most_one_succeed(client, settings, db_sessionmaker):
    """SQLite smoke only; the authoritative concurrency proof is tests/test_refresh_rotation_pg.py (PostgreSQL)."""
    import threading

    _session(client, settings)
    t0 = client.cookies[settings.REFRESH_COOKIE_NAME]
    client.cookies.clear()
    statuses, barrier = [], threading.Barrier(2)

    def tab():
        barrier.wait()
        r = client.post("/auth/refresh", headers={"Origin": FRONTEND, "Cookie": f"{settings.REFRESH_COOKIE_NAME}={t0}"})
        statuses.append(r.status_code)

    threads = [threading.Thread(target=tab) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(statuses).count(200) <= 1, f"both concurrent refreshes succeeded: {statuses}"
