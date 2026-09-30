"""Structured request/response logging — latency + status code per request,
correlated by request ID. FastAPI Backend Architecture Blueprint Section 17."""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger("app.request")

# Never log these — auth payloads carry passwords/tokens.
_SENSITIVE_PATHS = {"/auth/login", "/auth/register", "/auth/reset-password"}


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        logger.info(
            "request handled",
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "logged_body": request.url.path not in _SENSITIVE_PATHS,
                }
            },
        )
        return response
