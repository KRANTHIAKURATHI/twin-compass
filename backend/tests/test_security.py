"""Unit tests for app.core.security — no network, no database."""
from __future__ import annotations

import time

import jwt
import pytest

from app.core.exceptions import AuthenticationError
from app.core.security import verify_supabase_jwt
from tests.conftest import TEST_JWT_SECRET


def _make_token(*, exp_delta: int = 3600, secret: str = TEST_JWT_SECRET, sub: str = "11111111-1111-1111-1111-111111111111", aud: str = "authenticated") -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "email": "doc@example.com", "role": "authenticated", "aud": aud, "iat": now, "exp": now + exp_delta},
        secret,
        algorithm="HS256",
    )


def test_valid_token_verifies_successfully():
    token = _make_token()
    claims = verify_supabase_jwt(token)
    assert claims.sub == "11111111-1111-1111-1111-111111111111"
    assert claims.email == "doc@example.com"


def test_expired_token_is_rejected():
    token = _make_token(exp_delta=-10)
    with pytest.raises(AuthenticationError):
        verify_supabase_jwt(token)


def test_token_with_wrong_signature_is_rejected():
    token = _make_token(secret="a-completely-different-secret-value-here")
    with pytest.raises(AuthenticationError):
        verify_supabase_jwt(token)


def test_token_with_wrong_audience_is_rejected():
    token = _make_token(aud="some-other-audience")
    with pytest.raises(AuthenticationError):
        verify_supabase_jwt(token)


def test_malformed_token_is_rejected():
    with pytest.raises(AuthenticationError):
        verify_supabase_jwt("not-a-real-jwt")


def test_token_missing_required_claims_is_rejected():
    now = int(time.time())
    # Missing `sub` entirely.
    token = jwt.encode({"email": "doc@example.com", "aud": "authenticated", "exp": now + 3600}, TEST_JWT_SECRET, algorithm="HS256")
    with pytest.raises(AuthenticationError):
        verify_supabase_jwt(token)
