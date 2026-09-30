"""
Declarative base + shared column mixins.

Naming/typing conventions match the Database Architecture Blueprint Section
15.1 (snake_case tables/columns, `*_id` foreign keys, `*_at` timestamps) so
the ORM layer is a direct, unsurprising mirror of that document's table specs.

Portability note: columns use SQLAlchemy 2.0's dialect-neutral `sa.Uuid`
rather than `postgresql.UUID`. It renders as native `uuid` on PostgreSQL and
as `CHAR(32)` elsewhere, which is what lets the identical model layer back
both the Supabase/Postgres deployment and the SQLite file mode.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable constraint names, so Alembic autogenerate produces stable
# migrations instead of relying on backend-assigned names.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)


def uuid_col(**kwargs) -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(), **kwargs)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
