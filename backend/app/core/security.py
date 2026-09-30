"""
Access-token verification - one code path for both providers.

Supabase (HS256, signed with SUPABASE_JWT_SECRET) and the local provider
(HS256, signed with LOCAL_JWT_SECRET) issue the same claim shape, so
verification differs only in which key and audience are used. `Settings`
exposes those as `jwt_secret` / `jwt_audience`, and nothing above this
module needs to know which mode is active.

If a Supabase project is later switched to asymmetric signing keys
(RS256/ES256 + JWKS rotation), replace the decode call here with a cached
`PyJWKClient`; `app/dependencies/auth.py` is the only consumer.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import jwt
from jwt import InvalidTokenError

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError


@dataclass(frozen=True)
class TokenClaims:
    """The subset of a verified access-token payload we rely on."""

    sub: str
    email: str | None
    exp: int
    role: str | None  # the provider's own "authenticated" claim, NOT our app role


def verify_access_token(token: str) -> TokenClaims:
    """Verify signature, expiry and audience.

    Every failure mode - expired, malformed, wrong audience, bad signature -
    raises the same error, so a caller cannot learn which one occurred.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            options={"require": ["exp", "sub"]},
        )
    except InvalidTokenError as exc:
        raise AuthenticationError("Invalid or expired session token.") from exc

    return TokenClaims(
        sub=payload["sub"],
        email=payload.get("email"),
        exp=payload["exp"],
        role=payload.get("role"),
    )


def token_ttl_seconds(claims: TokenClaims) -> int:
    return max(0, claims.exp - int(time.time()))


# Backwards-compatible aliases: the original module exported these names.
SupabaseTokenClaims = TokenClaims
verify_supabase_jwt = verify_access_token
