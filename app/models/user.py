"""Domain objects: frozen pydantic models. No fastapi, sqlalchemy or asyncpg imports."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    # from_attributes: repos build these straight from ORM rows with `model_validate(row)`.
    model_config = ConfigDict(frozen=True, from_attributes=True)


class User(_Model):
    id: UUID
    email: str
    password_hash: str  # self-describing encoded hash; never the plaintext password
    created_at: datetime


class Session(_Model):
    """Result of a successful login."""

    access_token: str
    expires_in: int  # seconds
    user_id: UUID
