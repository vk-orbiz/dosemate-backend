"""Application settings. The ONLY place in the app that reads the environment (rule 9)."""

from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-secret-change-me-0123456789"
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    # Later files override earlier ones; real environment variables beat both.
    model_config = SettingsConfigDict(
        env_prefix="DOSEMATE_",
        env_file=(".env", ".env.production"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    database_url: str = "postgresql://dosemate:dosemate@localhost:5434/dosemate"
    db_pool_min_size: int = 1
    db_pool_max_size: int = 10

    jwt_secret: SecretStr = SecretStr(DEV_JWT_SECRET)
    jwt_ttl_seconds: int = 3600

    cors_origins: list[str] = []

    @model_validator(mode="after")
    def _check_jwt_secret(self) -> Self:
        secret = self.jwt_secret.get_secret_value()
        if len(secret) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(f"jwt_secret must be at least {MIN_JWT_SECRET_LENGTH} characters")
        if self.env == "production" and secret == DEV_JWT_SECRET:
            raise ValueError("jwt_secret must be changed from the development default")
        return self
