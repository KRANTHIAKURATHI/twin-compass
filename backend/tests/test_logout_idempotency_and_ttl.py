"""H5.2 / H5.3 backend facts the frontend relies on (test-only; no application code changed).

* Logout is idempotent: an unknown, missing, already-revoked or garbage refresh cookie is still a 200 and still
  clears the cookie, so a repeated or retried sign-out can never leave the UI in an error state.
* The access-token lifetime is exactly ACCESS_TOKEN_TTL_SECONDS (default 3600) and is env-configurable.
"""
from __future__ import annotations

import jwt
import pytest

from app.core.config import Settings, get_settings
from tests.conftest import login, register

ORIGIN = "http://localhost:5173"  # in the default CORS_ALLOWED_ORIGINS


def _cookie_cleared(response, name):
    header = response.headers.get("set-cookie", "")
    return name in header and ("max-age=0" in header.lower() or 'expires=' in header.lower())


def test_logout_twice_is_a_200_both_times(client, settings):
    register(client)
    cookie = login(client).cookies[settings.REFRESH_COOKIE_NAME]
    first = client.post("/auth/logout", headers={"Origin": ORIGIN})
    assert first.status_code == 200
    second = client.post("/auth/logout", headers={"Origin": ORIGIN, "Cookie": f"{settings.REFRESH_COOKIE_NAME}={cookie}"})
    assert second.status_code == 200 and _cookie_cleared(second, settings.REFRESH_COOKIE_NAME)


def test_logout_without_or_with_a_garbage_cookie_is_a_200(client, settings):
    assert client.post("/auth/logout", headers={"Origin": ORIGIN}).status_code == 200
    r = client.post("/auth/logout", headers={"Origin": ORIGIN, "Cookie": f"{settings.REFRESH_COOKIE_NAME}=not-a-real-token"})
    assert r.status_code == 200 and _cookie_cleared(r, settings.REFRESH_COOKIE_NAME)


def test_logout_after_the_session_was_revoked_still_succeeds_and_refresh_stays_rejected(client, settings):
    register(client)
    cookie = login(client).cookies[settings.REFRESH_COOKIE_NAME]
    client.cookies.clear()
    for _ in range(3):  # retries after the server already revoked it
        r = client.post("/auth/logout", headers={"Origin": ORIGIN, "Cookie": f"{settings.REFRESH_COOKIE_NAME}={cookie}"})
        assert r.status_code == 200
    refresh = client.post("/auth/refresh", headers={"Origin": ORIGIN, "Cookie": f"{settings.REFRESH_COOKIE_NAME}={cookie}"})
    assert refresh.status_code == 401, "a revoked refresh session cannot be restored"


# --- H5.3: access-token lifetime ----------------------------------------------------------------------

def test_access_token_lifetime_is_exactly_the_configured_ttl(client, settings):
    register(client)
    body = login(client).json()
    claims = jwt.decode(body["accessToken"], options={"verify_signature": False})
    assert claims["exp"] - claims["iat"] == get_settings().ACCESS_TOKEN_TTL_SECONDS


def test_access_token_ttl_default_is_one_hour_and_can_be_overridden_by_the_environment(monkeypatch):
    assert Settings.model_fields["ACCESS_TOKEN_TTL_SECONDS"].default == 3600
    monkeypatch.setenv("ACCESS_TOKEN_TTL_SECONDS", "900")
    assert Settings().ACCESS_TOKEN_TTL_SECONDS == 900


@pytest.mark.parametrize("legacy_name", ["ACCESS_TOKEN_EXPIRE_MINUTES", "JWT_EXPIRE_MINUTES"])
def test_legacy_expiry_variable_names_have_no_effect(monkeypatch, legacy_name):
    """backend/env.example documents ACCESS_TOKEN_EXPIRE_MINUTES; the setting that exists is ACCESS_TOKEN_TTL_SECONDS."""
    monkeypatch.setenv(legacy_name, "1440")
    assert Settings().ACCESS_TOKEN_TTL_SECONDS != 1440 * 60, "the legacy name must not silently extend the token lifetime"
