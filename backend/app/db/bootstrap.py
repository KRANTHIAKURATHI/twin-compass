"""
Database bootstrap.

File mode has to work immediately after `pip install -r requirements.txt`,
so on startup the SQLite schema is created if missing and the `roles`
reference rows are seeded. Against PostgreSQL the schema belongs to Alembic:
nothing is created implicitly, we only confirm the migration has been run and
say so clearly if it has not, rather than failing later with a confusing
"relation does not exist" on the first login.
"""
from __future__ import annotations

from sqlalchemy import inspect, select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_engine, get_sessionmaker
from app.models.base import Base
from app.models.identity import SEED_ROLES, Role

logger = get_logger(__name__)


async def create_schema_if_missing() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_roles() -> None:
    """Idempotent: inserts only the reference roles that are absent."""
    async with get_sessionmaker()() as session:
        existing = {name for name in (await session.execute(select(Role.name))).scalars()}
        added = [
            Role(id=rid, name=name, description=desc)
            for rid, name, desc in SEED_ROLES
            if name not in existing
        ]
        if added:
            session.add_all(added)
            await session.commit()
            logger.info(
                "seeded roles", extra={"extra_fields": {"roles": [r.name for r in added]}}
            )


async def ensure_database_ready() -> None:
    settings = get_settings()

    if settings.is_sqlite:
        await create_schema_if_missing()
        await seed_roles()
        logger.info(
            "sqlite database ready", extra={"extra_fields": {"url": settings.DATABASE_URL}}
        )
        return

    engine = get_engine()
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
    if "profiles" not in tables:
        raise RuntimeError(
            "The 'profiles' table is missing. Run `alembic upgrade head` against "
            f"{settings.DATABASE_URL.split('@')[-1]} before starting the API."
        )
    await seed_roles()
