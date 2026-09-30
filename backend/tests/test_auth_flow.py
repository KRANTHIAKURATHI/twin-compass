"""
End-to-end auth tests against the REAL service, repository and local
provider, on a real SQLite database. Nothing below is stubbed.

These are the tests that would have caught the AmbiguousForeignKeysError
that made every database-touching endpoint return 500.
"""
from __future__ import annotations

import time

import jwt
import pytest

from tests.conftest import TEST_JWT_SECRET, login, register


# --- registration -----------------------------------------------------------

def test_register_creates_profile_and_role(client):
    r = register(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["data"]["email"] == "doc@example.com"
    assert body["data"]["role"] == "doctor"
    assert "password" not in r.text.lower()


def test_register_rejects_duplicate_email_case_insensitively(client):
    assert register(client, email="dup@example.com").status_code == 201
    # Same address, different casing and padding - must still collide.
    r = register(client, email="  DUP@Example.COM ")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONFLICT"
    assert r.json()["error"]["field"] == "email"


def test_register_rejects_admin_self_assignment(client):
    r = register(client, email="sneaky@example.com", role="admin")
    assert r.status_code == 422  # excluded by the SelfServeRole literal


@pytest.mark.parametrize("password", ["short1", "alllettersnodigits", "12345678"])
def test_register_enforces_password_policy(client, password):
    r = register(client, email="weak@example.com", password=password)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_register_rejects_invalid_email(client):
    assert register(client, email="not-an-email").status_code == 422


def test_register_rejects_blank_name(client):
    assert register(client, name="   ").status_code == 422


# --- login ------------------------------------------------------------------

def test_login_returns_session_and_sets_httponly_cookie(client, settings):
    register(client)
    r = login(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["email"] == "doc@example.com"
    assert body["accessToken"]
    assert "refresh" not in r.text.lower()  # refresh token never in the body

    cookie_header = r.headers.get("set-cookie", "")
    assert settings.REFRESH_COOKIE_NAME in cookie_header
    assert "httponly" in cookie_header.lower()


def test_login_with_wrong_password_is_401(client):
    register(client)
    r = login(client, password="wrongpass1")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTHENTICATION_ERROR"


def test_login_for_unknown_email_gives_the_same_error(client):
    r = login(client, email="nobody@example.com", password="secret123")
    assert r.status_code == 401
    # Identical message to a wrong password - no account enumeration.
    assert r.json()["error"]["message"] == "Invalid email or password."


def test_login_is_case_insensitive_on_email(client):
    register(client, email="Case@Example.com")
    assert login(client, email="case@example.com").status_code == 200


# --- the access token actually works ---------------------------------------

def test_me_returns_the_real_user_via_the_real_dependency(client):
    register(client)
    token = login(client).json()["accessToken"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "doc@example.com"
    assert r.json()["role"] == "doctor"


def test_me_without_a_token_is_401(client):
    assert client.get("/auth/me").status_code == 401


def test_me_with_a_garbage_token_is_401(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


def test_well_signed_token_for_unknown_user_is_401_not_500(client):
    token = jwt.encode(
        {"sub": "11111111-1111-1111-1111-111111111111", "aud": "authenticated",
         "exp": int(time.time()) + 600},
        TEST_JWT_SECRET, algorithm="HS256",
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_well_signed_token_with_non_uuid_sub_is_401_not_500(client):
    token = jwt.encode(
        {"sub": "definitely-not-a-uuid", "aud": "authenticated", "exp": int(time.time()) + 600},
        TEST_JWT_SECRET, algorithm="HS256",
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


# --- refresh rotation -------------------------------------------------------

def test_refresh_rotates_the_token(client, settings):
    register(client)
    first = login(client).cookies[settings.REFRESH_COOKIE_NAME]
    r = client.post("/auth/refresh")
    assert r.status_code == 200, r.text
    second = r.cookies[settings.REFRESH_COOKIE_NAME]
    assert second != first, "refresh token must rotate on use"
    assert r.json()["accessToken"]


def test_replaying_a_used_refresh_token_is_rejected(client, settings):
    register(client)
    stolen = login(client).cookies[settings.REFRESH_COOKIE_NAME]
    assert client.post("/auth/refresh").status_code == 200  # rotates `stolen`

    client.cookies.clear()
    client.cookies.set(settings.REFRESH_COOKIE_NAME, stolen)
    replay = client.post("/auth/refresh")
    assert replay.status_code == 401, "a rotated refresh token must not be reusable"


def test_refresh_without_a_cookie_is_401(client):
    assert client.post("/auth/refresh").status_code == 401


# --- logout -----------------------------------------------------------------

def test_logout_clears_cookie_and_revokes_the_refresh_token(client, settings):
    register(client)
    token = login(client).cookies[settings.REFRESH_COOKIE_NAME]

    out = client.post("/auth/logout")
    assert out.status_code == 200
    assert out.json()["ok"] is True

    client.cookies.clear()
    client.cookies.set(settings.REFRESH_COOKIE_NAME, token)
    assert client.post("/auth/refresh").status_code == 401, "logout must revoke server-side"


# --- password reset ---------------------------------------------------------

def _reset_token_from_log(settings) -> str:
    log = settings.DATA_DIR / "password-reset-links.log"
    return log.read_text(encoding="utf-8").strip().splitlines()[-1].split("token=")[-1]


def test_forgot_password_response_is_identical_for_unknown_emails(client):
    register(client)
    known = client.post("/auth/forgot-password", json={"email": "doc@example.com"})
    unknown = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


def test_full_reset_flow_changes_the_password(client, settings):
    register(client)
    assert client.post("/auth/forgot-password", json={"email": "doc@example.com"}).status_code == 200

    token = _reset_token_from_log(settings)
    r = client.post("/auth/reset-password", json={"token": token, "password": "brandnew123"})
    assert r.status_code == 200, r.text

    assert login(client, password="secret123").status_code == 401
    assert login(client, password="brandnew123").status_code == 200


def test_reset_token_is_single_use(client, settings):
    register(client)
    client.post("/auth/forgot-password", json={"email": "doc@example.com"})
    token = _reset_token_from_log(settings)
    assert client.post("/auth/reset-password", json={"token": token, "password": "brandnew123"}).status_code == 200
    again = client.post("/auth/reset-password", json={"token": token, "password": "another1234"})
    assert again.status_code == 401


def test_reset_password_enforces_the_same_policy_as_register(client, settings):
    register(client)
    client.post("/auth/forgot-password", json={"email": "doc@example.com"})
    token = _reset_token_from_log(settings)
    # "alllettersnodigits" is refused at registration; it must be refused here too.
    r = client.post("/auth/reset-password", json={"token": token, "password": "alllettersnodigits"})
    assert r.status_code == 422


def test_reset_password_revokes_existing_sessions(client, settings):
    register(client)
    old_refresh = login(client).cookies[settings.REFRESH_COOKIE_NAME]
    client.post("/auth/forgot-password", json={"email": "doc@example.com"})
    token = _reset_token_from_log(settings)
    client.post("/auth/reset-password", json={"token": token, "password": "brandnew123"})

    client.cookies.clear()
    client.cookies.set(settings.REFRESH_COOKIE_NAME, old_refresh)
    assert client.post("/auth/refresh").status_code == 401


def test_bogus_reset_token_is_401_not_500(client):
    r = client.post("/auth/reset-password", json={"token": "made-up", "password": "brandnew123"})
    assert r.status_code == 401


# --- profile ----------------------------------------------------------------

def test_update_profile_persists(client):
    register(client)
    token = login(client).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.patch("/users/profile", json={"name": "Dr. Updated", "title": "Chief"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Dr. Updated"

    again = client.get("/auth/me", headers=headers)
    assert again.json()["name"] == "Dr. Updated"
    assert again.json()["title"] == "Chief"


def test_update_profile_cannot_escalate_role(client):
    register(client)
    token = login(client).json()["accessToken"]
    r = client.patch("/users/profile", json={"role": "admin"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422  # extra="forbid"


def test_update_profile_requires_auth(client):
    assert client.patch("/users/profile", json={"name": "X"}).status_code == 401


def test_avatar_url_camelcase_alias_round_trips(client):
    register(client)
    token = login(client).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.patch("/users/profile", json={"avatarUrl": "https://cdn.example.com/a.png"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["avatarUrl"] == "https://cdn.example.com/a.png"


# --- ops --------------------------------------------------------------------

def test_health_and_readiness(client):
    assert client.get("/health").json()["status"] == "ok"
    ready = client.get("/health/ready").json()
    assert ready["database_ok"] is True
    assert ready["auth_provider"] == "local"
