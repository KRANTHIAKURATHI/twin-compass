"""
Global exception handling.

Maps every raised exception to the standard error envelope defined in the
System Architecture Blueprint Section 12.1:

    { "error": { "code", "message", "field", "request_id" } }

registered via `app.add_exception_handler(...)` in main.py rather than
per-route try/except, so the response shape is guaranteed consistent no
matter which layer raises (FastAPI Backend Architecture Blueprint Section
14: "Exception Handling").
"""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.exceptions import AppError
from app.core.logging import get_logger, request_id_var

logger = get_logger(__name__)


def _envelope(code: str, message: str, *, field: str | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "field": field,
            "request_id": request_id_var.get(),
        }
    }


class ServerErrorEnvelopeMiddleware:
    """Turns an unhandled exception into the standard envelope from *inside*
    the CORS layer.

    Starlette attaches the `@app.exception_handler(Exception)` handler below
    to `ServerErrorMiddleware`, which is always the outermost middleware —
    outside `CORSMiddleware`. A 500 produced there therefore carries no
    `Access-Control-Allow-Origin` header, so a browser discards the response
    and reports a CORS failure (`net::ERR_FAILED`) instead of the real
    server error: the actual cause never reaches the developer console and
    the frontend sees a network error rather than a 500.

    Registering this as the innermost middleware produces the same envelope
    while the response is still on its way out through CORS, so the headers
    get attached and the real status/message survives. The `Exception`
    handler stays registered as a backstop for anything raised by the outer
    middleware itself.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def _send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception as exc:
            logger.exception("unhandled exception", exc_info=exc)
            # Headers are already on the wire - nothing can be rewritten, so
            # let it bubble to ServerErrorMiddleware, which aborts the
            # response.
            if response_started:
                raise
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=_envelope("INTERNAL_ERROR", "Something went wrong. Please try again."),
            )
            await response(scope, receive, send)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.exception("unhandled domain error", exc_info=exc)
        return JSONResponse(status_code=exc.status_code, content=_envelope(exc.code, exc.message, field=exc.field))

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic validation errors -> first offending field surfaced at
        # top level so the frontend's `ApiError.fieldErrors` can map
        # straight into react-hook-form's `setError` per the frontend's own
        # backend-integration-report.md.
        errors = exc.errors()
        field = ".".join(str(p) for p in errors[0]["loc"][1:]) if errors else None
        message = errors[0]["msg"] if errors else "Invalid request."
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope("VALIDATION_ERROR", message, field=field),
        )

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=_envelope("RATE_LIMITED", "Too many requests. Please wait before trying again."),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_envelope("HTTP_ERROR", str(exc.detail)))

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("INTERNAL_ERROR", "Something went wrong. Please try again."),
        )
