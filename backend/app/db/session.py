"""
SQLAlchemy 2.0 async engine + session factory, for both supported backends.

PostgreSQL / Supabase
    Driven by asyncpg. `NullPool` is used deliberately: Supabase fronts
    Postgres with PgBouncer in transaction mode, and a second client-side
    pool on top of a transaction-mode pooler breaks asyncpg's prepared
    statement cache (statements get planned on one backend connection and
    replayed on another). `statement_cache_size=0` disables that cache for
    the same reason. Point DATABASE_URL at the pooler endpoint (port 6543).

    The previous version documented NullPool but actually used the default
    QueuePool with pool_pre_ping - i.e. exactly the configuration its own
    comment warned against.

SQLite (file mode)
    A single file under DATA_DIR. `check_same_thread=False` is required
    because SQLAlchemy's async layer runs the driver in a worker thread.

The engine is created lazily so that importing any module (for tests, for
`alembic`, for `--help`) does not require a reachable database.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def build_engine(database_url: str | None = None) -> AsyncEngine:
    settings = get_settings()
    url = database_url or settings.DATABASE_URL
    kwargs: dict[str, Any] = {"echo": False, "future": True}

    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["poolclass"] = NullPool
        kwargs["pool_pre_ping"] = True
        if "asyncpg" in url:
            kwargs["connect_args"] = {
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
                "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4().hex}__",
            }

    return create_async_engine(url, **kwargs)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False, autoflush=False
        )
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one session per request.

    Rolls back on any exception so a failed request can never leave a
    half-applied transaction to be committed by whatever runs next on this
    connection.
    """
    async with get_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
