"""Refresh-cookie attributes for the cross-site (frontend and API on different sites) deployment."""
from __future__ import annotations

import pytest

from app.api.v1.routers import auth as auth_router
from app.core.config import Settings, get_settings
from tests.conftest import login, register


def _cross_site(monkeypatch):
    patched = get_settings().model_copy(update={"REFRESH_COOKIE_SAMESITE": "none", "REFRESH_COOKIE_SECURE": True})
    monkeypatch.setattr(auth_router, "settings", patched)


def _attrs(header: str) -> set[str]:
    return {part.strip().lower() for part in header.split(";")[1:]}


def test_samesite_none_requires_secure():
    with pytest.raises(ValueError, match="SAMESITE=none requires REFRESH_COOKIE_SECURE"):
        Settings(REFRESH_COOKIE_SAMESITE="none", REFRESH_COOKIE_SECURE=False)


def test_login_cookie_is_httponly_secure_samesite_none_when_cross_site(client, monkeypatch):
    _cross_site(monkeypatch)
    register(client, email="xsite@example.com", role="doctor")
    header = login(client, email="xsite@example.com").headers["set-cookie"]
    assert header.startswith(f"{get_settings().REFRESH_COOKIE_NAME}=")
    assert {"httponly", "secure", "samesite=none", "path=/"} <= _attrs(header)
    assert not any(a.startswith("domain=") for a in _attrs(header))  # host-only: stays on the API origin


def test_logout_clears_cookie_with_matching_attributes(client, monkeypatch):
    _cross_site(monkeypatch)
    register(client, email="xsite2@example.com", role="doctor")
    login(client, email="xsite2@example.com")
    r = client.post("/auth/logout")
    cleared = [h for h in r.headers.get_list("set-cookie") if h.startswith(get_settings().REFRESH_COOKIE_NAME)]
    assert cleared, r.headers
    assert {"httponly", "secure", "samesite=none", "path=/", "max-age=0"} <= _attrs(cleared[0])
