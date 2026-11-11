"""Origin / Fetch-Metadata check for the endpoints that act on the refresh cookie.

`/auth/refresh` and `/auth/logout` authenticate with an ambient cookie, so they need an explicit
cross-site request defence; CORS is not one (it only stops a page from *reading* a response, the
side effect - rotating or revoking the session - still happens). SameSite=Lax is the first layer;
this is the second.

Decision order:
  1. `Origin` present (every browser sends it on a POST): it must equal an entry of
     CORS_ALLOWED_ORIGINS. `Origin: null` and anything unlisted is rejected. Same-origin requests
     arriving through the Vercel `/api` rewrite carry the frontend's own origin, which is that list.
  2. No `Origin` but `Sec-Fetch-Site` present: only `same-origin` / `none` pass; `same-site` and
     `cross-site` are rejected.
  3. Neither header: a non-browser caller (curl, server-to-server, the test client). A cross-site
     attack needs a victim's browser, and browsers always send one of the two headers on a POST,
     so this is not a CSRF vector. Allowed by design.
"""
from __future__ import annotations

from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import AuthorizationError
from app.core.logging import get_logger, log_security_event

logger = get_logger(__name__)

_SAME_SITE_VALUES = {"same-origin", "none"}


def _normalise(origin: str) -> str:
    return origin.strip().rstrip("/").lower()


async def require_trusted_origin(request: Request) -> None:
    settings = get_settings()
    origin = request.headers.get("origin")
    if origin is not None:
        allowed = {_normalise(o) for o in settings.CORS_ALLOWED_ORIGINS if o != "*"}
        if _normalise(origin) in allowed:
            return
        reason = "origin_not_allowed"
    else:
        site = request.headers.get("sec-fetch-site")
        if site is None or site.strip().lower() in _SAME_SITE_VALUES:
            return
        reason = "cross_site_fetch_metadata"

    log_security_event(
        logger,
        "csrf.rejected",
        reason=reason,
        path=request.url.path,
        origin=origin,
        sec_fetch_site=request.headers.get("sec-fetch-site"),
    )
    raise AuthorizationError("Cross-site request rejected.")
