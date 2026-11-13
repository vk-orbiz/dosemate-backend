"""Shared fixtures. Integration fixtures run against a real Postgres server: they create
a throwaway database on the server named by `Settings().database_url`, and drop it after.
Run `pytest tests/unit` if you have no database."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
from uuid import uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import text

from app.core.config import Settings
from app.main import build_app


@asynccontextmanager
async def _throwaway_database(prefix: str) -> AsyncIterator[str]:
    """Create an empty database on the server in `Settings().database_url`; drop it after."""
    base = Settings().database_url
    admin_url = urlsplit(base)._replace(path="/postgres").geturl()
    name = f"{prefix}_{uuid4().hex[:8]}"
    try:
        admin = await asyncpg.connect(admin_url)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.fail(f"integration tests need Postgres at {admin_url!r}: {exc}")
    await admin.execute(f'CREATE DATABASE "{name}"')
    try:
        yield urlsplit(base)._replace(path=f"/{name}").geturl()
    finally:
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


@pytest_asyncio.fixture(scope="session")
async def test_database_url() -> AsyncIterator[str]:
    async with _throwaway_database("dosemate_test") as url:
        yield url


@pytest_asyncio.fixture
async def scratch_database_url() -> AsyncIterator[str]:
    """An empty database per test (migration tests)."""
    async with _throwaway_database("dosemate_scratch") as url:
        yield url


@pytest_asyncio.fixture
async def scratch_database_url_2() -> AsyncIterator[str]:
    """A second, independent empty database (for comparing two schemas)."""
    async with _throwaway_database("dosemate_scratch") as url:
        yield url


@pytest_asyncio.fixture(scope="session")
async def app(test_database_url: str) -> AsyncIterator[FastAPI]:
    settings = Settings(
        env="test",
        log_level="WARNING",
        database_url=test_database_url,
        jwt_secret=SecretStr("integration-test-secret-0123456789abcdef"),
    )
    application = build_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.state.engine.begin() as conn:
        await conn.execute(text("TRUNCATE users CASCADE"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
