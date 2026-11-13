"""Alembic environment (async). Target metadata is the ORM models.

The URL comes from `config.attributes["url"]` (set by `migrate.py`) or, for the dev CLI,
from `Settings` (the only reader of the environment; rule 9). Nothing is read from alembic.ini.
"""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import SchemaItem

import app.storage.postgres.models  # noqa: F401  (registers every table on Base.metadata)
from app.core.config import Settings
from app.storage.postgres.base import Base
from app.storage.postgres.engine import build_engine, to_async_url

config = context.config
target_metadata = Base.metadata


# Created by the removed hand-rolled migrator and kept for one release as a rollback safety net.
# Not in the models, so without this autogenerate and `alembic check` would propose dropping it.
_LEGACY_TABLES = {"schema_migrations"}


def _include_object(
    obj: SchemaItem, name: str | None, type_: str, reflected: bool, compare_to: SchemaItem | None
) -> bool:
    return not (type_ == "table" and name in _LEGACY_TABLES)


def _url() -> str:
    url = config.attributes.get("url")
    return url if isinstance(url, str) else Settings().database_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout (`alembic upgrade head --sql`) for review; no database needed."""
    context.configure(
        url=to_async_url(_url()),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = build_engine(_url(), poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
