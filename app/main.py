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
from app.storage.postgres.engine import build_engine, build_sessionmaker
from app.storage.postgres.migrate import migrate
from app.transport.http.server import create_app


def build_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logger = ConsoleLogger(settings.log_level)

    # storage + repo
    engine = build_engine(
        settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    user_repo = UserRepo(build_sessionmaker(engine))

    # service
    secret = settings.jwt_secret.get_secret_value()
    jwt_service = JWTService(secret, settings.jwt_ttl_seconds)
    auth_service = AuthService(user_repo, jwt_service)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            if settings.migrate_on_startup:
                await migrate(settings.database_url, logger)
            yield
        finally:
            await engine.dispose()

    app = create_app(settings, lifespan)
    app.state.settings = settings
    app.state.logger = logger
    app.state.engine = engine
    app.state.jwt_service = jwt_service
    app.state.auth_service = auth_service
    return app


app = build_app()
