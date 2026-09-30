"""
FastAPI application entrypoint — Module 1 (Authentication & Authorization) only.

Route mounting note: the frontend's `src/services/endpoints.ts` and this
task's brief both specify bare paths (`/auth/login`, not
`/api/v1/auth/login`), so the router is mounted once, unprefixed, to match
that contract exactly.

A `/api/v1` prefix (per the System Architecture Blueprint's general
API-versioning convention, Section 11.1) is a reasonable future evolution,
but registering the *same* `APIRouter` instance under two prefixes on one
FastAPI app corrupts FastAPI's internal dependant-resolution cache — this
was verified empirically while implementing this module (a request body
parameter gets misclassified as a query parameter on the second
registration). The correct way to expose both a versioned and unversioned
surface, if ever needed, is two independent `APIRouter` instances built
from the same route-handler functions, or a reverse-proxy rewrite rule —
not a second `include_router` call on the same object.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.api.v1.routers.auth import limiter
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.middleware.exception_handler import (
    ServerErrorEnvelopeMiddleware,
    register_exception_handlers,
)
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.request_id import RequestIdMiddleware

settings = get_settings()
configure_logging()
logger = get_logger("app.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "OncoTwin API starting",
        extra={
            "extra_fields": {
                "environment": settings.ENVIRONMENT,
                "auth_provider": settings.AUTH_PROVIDER,
                "database": "sqlite" if settings.is_sqlite else "postgresql",
            }
        },
    )
    # File mode is meant to work straight after `pip install`, so the schema
    # and the seed roles are created on boot if absent. Against Postgres the
    # schema is owned by Alembic and this only verifies connectivity.
    from app.db.bootstrap import ensure_database_ready

    await ensure_database_ready()
    yield
    from app.db.session import dispose_engine

    await dispose_engine()
    logger.info("OncoTwin API shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description=(
        "OncoTwin backend — Module 1 (Authentication & Authorization) only. "
        "See docs/module-1-auth-summary.md for scope and design decisions."
    ),
    lifespan=lifespan,
)

# --- Middleware stack -------------------------------------------------------
# Starlette applies middleware in REVERSE registration order: the last one
# added ends up outermost. The original code registered RequestId first
# intending it to run first, which actually made it innermost - so
# LoggingMiddleware ran outside the request-id context and every access log
# was emitted with "request_id": null, defeating the correlation it exists
# for. Registration below is therefore deliberately inside-out, giving the
# intended runtime order:
#
#   RequestId (outermost: the correlation id must exist before anything logs)
#     -> CORS
#       -> Logging (inside RequestId, so every access log carries the id)
#         -> RateLimit
#           -> ServerErrorEnvelope (innermost, so its 500 still passes back
#              out through CORS and gets the Allow-Origin header - see the
#              class docstring)
#             -> route + Depends(get_current_user)
app.add_middleware(ServerErrorEnvelopeMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,  # the refresh cookie needs credentials cross-origin
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestIdMiddleware)
app.state.limiter = limiter

register_exception_handlers(app)

# --- Routes -----------------------------------------------------------------
app.include_router(api_router)


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness only - deliberately does no I/O so it stays useful when the
    database is the thing that is down."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["ops"])
async def readiness() -> dict[str, object]:
    """Readiness: reports the configured mode and whether the database answers."""
    from sqlalchemy import text

    from app.db.session import get_sessionmaker

    database_ok = True
    detail: str | None = None
    try:
        async with get_sessionmaker()() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - depends on live infra
        database_ok = False
        detail = str(exc)

    return {
        "status": "ok" if database_ok else "degraded",
        "auth_provider": settings.AUTH_PROVIDER,
        "database": "sqlite" if settings.is_sqlite else "postgresql",
        "database_ok": database_ok,
        "detail": detail,
    }
