"""Alembic bootstrap against real throwaway databases: fresh, legacy cut-over, concurrency."""

import asyncio

import asyncpg
import pytest
from alembic import command
from alembic.script import ScriptDirectory

from app.core.logger import ConsoleLogger
from app.storage.postgres.migrate import MigrationError, alembic_config, migrate

LOGGER = ConsoleLogger("WARNING")

# Verbatim DDL of migration 1 of the removed hand-rolled migrator (the legacy schema).
LEGACY_USERS_DDL = """
    CREATE TABLE users (
        id            uuid        PRIMARY KEY,
        email         text        NOT NULL UNIQUE CHECK (email = lower(email)),
        password_hash text        NOT NULL,
        created_at    timestamptz NOT NULL
    )
"""
LEGACY_TRACKING_DDL = """
    CREATE TABLE schema_migrations (
        version    integer     PRIMARY KEY,
        applied_at timestamptz NOT NULL DEFAULT now()
    )
"""
USER_ROW = (
    "INSERT INTO users VALUES ('00000000-0000-0000-0000-000000000001', "
    "'a@example.com', 'hash', now())"
)

SCHEMA_QUERIES = {
    "columns": """SELECT column_name, data_type, is_nullable, column_default
                  FROM information_schema.columns WHERE table_name = 'users'
                  ORDER BY column_name""",
    "constraints": """SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
                      WHERE conrelid = 'users'::regclass ORDER BY conname""",
    "indexes": "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'users' ORDER BY 1",
}


async def _scalar(url: str, sql: str) -> object:
    conn = await asyncpg.connect(url)
    try:
        return await conn.fetchval(sql)
    finally:
        await conn.close()


async def _exec(url: str, *statements: str) -> None:
    conn = await asyncpg.connect(url)
    try:
        for sql in statements:
            await conn.execute(sql)
    finally:
        await conn.close()


async def _tables(url: str) -> set[str]:
    conn = await asyncpg.connect(url)
    try:
        rows = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        return {r["tablename"] for r in rows}
    finally:
        await conn.close()


async def _schema(url: str) -> dict[str, list[tuple[object, ...]]]:
    conn = await asyncpg.connect(url)
    try:
        return {
            k: [tuple(r.values()) for r in await conn.fetch(q)] for k, q in SCHEMA_QUERIES.items()
        }
    finally:
        await conn.close()


def test_single_head() -> None:
    heads = ScriptDirectory.from_config(alembic_config("postgresql://unused")).get_heads()
    assert len(heads) == 1, f"multiple migration heads (branch conflict?): {heads}"


async def test_fresh_database_upgrades_to_head(scratch_database_url: str) -> None:
    await migrate(scratch_database_url, LOGGER)

    assert await _tables(scratch_database_url) == {"users", "alembic_version"}
    assert await _scalar(scratch_database_url, "SELECT version_num FROM alembic_version") == "0001"


async def test_upgrade_is_idempotent(scratch_database_url: str) -> None:
    await migrate(scratch_database_url, LOGGER)
    await migrate(scratch_database_url, LOGGER)
    assert await _scalar(scratch_database_url, "SELECT version_num FROM alembic_version") == "0001"


async def test_legacy_database_is_stamped_not_rebuilt(scratch_database_url: str) -> None:
    await _exec(
        scratch_database_url,
        LEGACY_USERS_DDL,
        LEGACY_TRACKING_DDL,
        "INSERT INTO schema_migrations (version) VALUES (1)",
        USER_ROW,
    )

    await migrate(scratch_database_url, LOGGER)  # would fail with "already exists" if DDL re-ran

    assert await _scalar(scratch_database_url, "SELECT version_num FROM alembic_version") == "0001"
    assert await _scalar(scratch_database_url, "SELECT count(*) FROM users") == 1
    assert await _scalar(scratch_database_url, "SELECT count(*) FROM schema_migrations") == 1
    # The kept legacy table must not show up as drift (autogenerate would propose dropping it).
    await asyncio.to_thread(command.check, alembic_config(scratch_database_url))


@pytest.mark.parametrize("versions", [[2], [1, 2], [1, 3], []])
async def test_unexpected_legacy_history_fails_and_changes_nothing(
    scratch_database_url: str, versions: list[int]
) -> None:
    inserts = [f"INSERT INTO schema_migrations (version) VALUES ({v})" for v in versions]
    await _exec(scratch_database_url, LEGACY_USERS_DDL, LEGACY_TRACKING_DDL, *inserts)

    with pytest.raises(MigrationError):
        await migrate(scratch_database_url, LOGGER)

    assert await _tables(scratch_database_url) == {"users", "schema_migrations"}


async def test_tables_without_history_fail_and_change_nothing(scratch_database_url: str) -> None:
    await _exec(scratch_database_url, LEGACY_USERS_DDL)

    with pytest.raises(MigrationError):
        await migrate(scratch_database_url, LOGGER)

    assert await _tables(scratch_database_url) == {"users"}


async def test_concurrent_bootstraps_have_no_error(scratch_database_url: str) -> None:
    await asyncio.gather(*(migrate(scratch_database_url, LOGGER) for _ in range(4)))
    assert await _scalar(scratch_database_url, "SELECT version_num FROM alembic_version") == "0001"


async def test_downgrade_upgrade_round_trip(scratch_database_url: str) -> None:
    cfg = alembic_config(scratch_database_url)
    await migrate(scratch_database_url, LOGGER)

    await asyncio.to_thread(command.downgrade, cfg, "base")
    assert "users" not in await _tables(scratch_database_url)

    await asyncio.to_thread(command.upgrade, cfg, "head")
    assert "users" in await _tables(scratch_database_url)


async def test_models_and_migrations_have_no_drift(scratch_database_url: str) -> None:
    await migrate(scratch_database_url, LOGGER)
    # Raises if autogenerate would produce a new revision (a model changed without one).
    await asyncio.to_thread(command.check, alembic_config(scratch_database_url))


async def test_alembic_schema_matches_legacy_schema(
    scratch_database_url: str, scratch_database_url_2: str
) -> None:
    await _exec(scratch_database_url, LEGACY_USERS_DDL)
    await migrate(scratch_database_url_2, LOGGER)

    assert await _schema(scratch_database_url_2) == await _schema(scratch_database_url)
