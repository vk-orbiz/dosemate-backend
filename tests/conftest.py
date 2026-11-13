"""Shared fixtures. Integration fixtures run against a real Postgres server: they create
a throwaway database on the server named by `Settings().database_url`, and drop it after.
Run `pytest tests/unit` if you have no database."""

from collections.abc import AsyncIterator
from urllib.parse import urlsplit
from uuid import uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from pydantic import SecretStr

from app.core.config import Settings
from app.main import build_app
from app.storage.postgres import tables


@pytest_asyncio.fixture(scope="session")
async def test_database_url() -> AsyncIterator[str]:
    base = Settings().database_url
    admin_url = urlsplit(base)._replace(path="/postgres").geturl()
    name = f"dosemate_test_{uuid4().hex[:8]}"
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
    await app.state.db.pool.execute(f"TRUNCATE {tables.USERS} CASCADE")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
