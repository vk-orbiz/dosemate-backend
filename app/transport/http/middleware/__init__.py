from fastapi import FastAPI

from app.core.config import Settings
from app.transport.http.middleware.cors import add_cors


def add_middlewares(app: FastAPI, settings: Settings) -> None:
    add_cors(app, settings.cors_origins)
