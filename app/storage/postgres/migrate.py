"""Schema migration entry point: `python -m app.storage.postgres.migrate`.

Also called from the app lifespan when `Settings.migrate_on_startup` is true. Runs
`alembic upgrade head` under a Postgres advisory lock, and adopts databases created by the
old hand-rolled migrator (`schema_migrations`) by stamping them instead of re-running DDL.
"""

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.logger import ConsoleLogger, Logger
from app.storage.postgres.engine import build_engine

_LOCK_ID = 7_265_001  # same id the old runner used, so old and new instances exclude each other
_LEGACY_TABLE = "schema_migrations"

# Legacy `schema_migrations.version` -> the Alembic revision whose schema is identical to it.
# Frozen: legacy versions never grow; new schema changes are new Alembic revisions.
_LEGACY_REVISIONS = {1: "0001"}


class MigrationError(RuntimeError):
    """The database is in a state we will not touch automatically."""


def alembic_config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    cfg.attributes["url"] = url
    return cfg


async def _exists(conn: AsyncConnection, table: str) -> bool:
    row = await conn.execute(text("SELECT to_regclass(:name) IS NOT NULL"), {"name": table})
    return bool(row.scalar_one())


async def _legacy_revision(conn: AsyncConnection) -> str:
    """The revision to stamp for a legacy database, or raise if its history is unusual."""
    rows = await conn.execute(text(f"SELECT version FROM {_LEGACY_TABLE} ORDER BY version"))
    versions = [int(v) for v in rows.scalars()]
    known = sorted(_LEGACY_REVISIONS)
    if not versions or versions != known[: len(versions)]:
        raise MigrationError(
            f"{_LEGACY_TABLE} holds versions {versions}; expected a contiguous prefix of "
            f"{known}. Refusing to touch the database."
        )
    return _LEGACY_REVISIONS[versions[-1]]


async def migrate(database_url: str, logger: Logger) -> None:
    cfg = alembic_config(database_url)
    engine = build_engine(database_url, poolclass=NullPool)
    try:
        # A dedicated autocommit connection holds the session-level lock; Alembic uses its own.
        async with engine.connect() as lock:
            lock = await lock.execution_options(isolation_level="AUTOCOMMIT")
            await lock.execute(text("SELECT pg_advisory_lock(:id)"), {"id": _LOCK_ID})
            try:
                if await _exists(lock, "alembic_version"):
                    pass
                elif await _exists(lock, _LEGACY_TABLE):
                    revision = await _legacy_revision(lock)
                    await asyncio.to_thread(command.stamp, cfg, revision)
                    logger.info("adopted legacy migration history", revision=revision)
                elif await _exists(lock, "users"):
                    raise MigrationError(
                        "tables exist but there is no migration history; refusing to guess"
                    )
                await asyncio.to_thread(command.upgrade, cfg, "head")
                logger.info("database is at head")
            finally:
                await lock.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": _LOCK_ID})
    finally:
        await engine.dispose()


def main() -> None:
    settings = Settings()
    asyncio.run(migrate(settings.database_url, ConsoleLogger(settings.log_level)))


if __name__ == "__main__":
    main()
