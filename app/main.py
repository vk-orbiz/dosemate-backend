"""Composition root (rule 5): the only module that knows every layer.

Builds all objects with manual constructor injection and stores them on `app.state`.
Dependency direction: transport -> service -> (protocols) <- repo -> storage.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import Settings
from app.core.logger import ConsoleLogger
from app.repo.user import UserRepo
from app.service.auth import AuthService
from app.service.jwt import JWTService
from app.storage.postgres.db import Postgres
from app.transport.http.handlers.auth import AuthHandler
from app.transport.http.server import create_app


def build_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logger = ConsoleLogger(settings.log_level)

    # storage + repo
    db = Postgres(
        settings.database_url,
        logger,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    user_repo = UserRepo(db)

    # service
    secret = settings.jwt_secret.get_secret_value()
    jwt_service = JWTService(secret, settings.jwt_ttl_seconds)
    auth_service = AuthService(user_repo, jwt_service)

    # transport
    auth_handler = AuthHandler(auth_service)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await db.connect()
        try:
            await db.run_migrations()
            yield
        finally:
            await db.close()

    app = create_app(settings, lifespan)
    app.state.settings = settings
    app.state.logger = logger
    app.state.db = db
    app.state.jwt_service = jwt_service
    app.state.auth_service = auth_service
    app.state.auth_handler = auth_handler
    return app


app = build_app()
