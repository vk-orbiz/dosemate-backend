"""Postgres connection pool and schema migrations.

Only DDL lives here. Every query against application data lives in `repo/` (rule 7).
"""

# asyncpg.Pool is only generic in the stubs, not at runtime, so annotations stay lazy.
from __future__ import annotations

import asyncpg

from app.core.logger import Logger
from app.storage.postgres import tables

_MIGRATION_LOCK_ID = 7_265_001  # arbitrary; serialises concurrent app starts

_MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        f"""
        CREATE TABLE {tables.USERS} (
            id            uuid        PRIMARY KEY,
            email         text        NOT NULL UNIQUE CHECK (email = lower(email)),
            password_hash text        NOT NULL,
            created_at    timestamptz NOT NULL
        );
        """,
    ),
)


class Postgres:
    """Owns the asyncpg pool. Constructed unconnected in `main.py`; connected in lifespan."""

    def __init__(self, dsn: str, logger: Logger, *, min_size: int = 1, max_size: int = 10) -> None:
        self._dsn = dsn
        self._logger = logger
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool[asyncpg.Record] | None = None

    @property
    def pool(self) -> asyncpg.Pool[asyncpg.Record]:
        if self._pool is None:
            raise RuntimeError("Postgres pool is not connected; call connect() first")
        return self._pool

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            self._dsn, min_size=self._min_size, max_size=self._max_size
        )
        self._logger.info("postgres pool created")

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._logger.info("postgres pool closed")

    async def run_migrations(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("SELECT pg_advisory_lock($1)", _MIGRATION_LOCK_ID)
            try:
                await conn.execute(
                    f"""CREATE TABLE IF NOT EXISTS {tables.SCHEMA_MIGRATIONS} (
                        version    integer     PRIMARY KEY,
                        applied_at timestamptz NOT NULL DEFAULT now()
                    )"""
                )
                rows = await conn.fetch(f"SELECT version FROM {tables.SCHEMA_MIGRATIONS}")
                applied = {row["version"] for row in rows}
                for version, ddl in _MIGRATIONS:
                    if version in applied:
                        continue
                    async with conn.transaction():
                        await conn.execute(ddl)
                        await conn.execute(
                            f"INSERT INTO {tables.SCHEMA_MIGRATIONS} (version) VALUES ($1)",
                            version,
                        )
                    self._logger.info("migration applied", version=version)
            finally:
                await conn.execute("SELECT pg_advisory_unlock($1)", _MIGRATION_LOCK_ID)
