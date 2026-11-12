"""Data access for users. Returns domain models, raises domain errors (rules 3, 4, 7)."""

import asyncpg

from app.core.errors import EmailAlreadyExists, UserNotFound
from app.models.user import User
from app.repo.entities.user import UserEntity
from app.storage.postgres import tables
from app.storage.postgres.db import Postgres

_INSERT = f"""
    INSERT INTO {tables.USERS} (id, email, password_hash, created_at)
    VALUES ($1, $2, $3, $4)
"""
_GET_BY_EMAIL = f"""
    SELECT id, email, password_hash, created_at
    FROM {tables.USERS}
    WHERE email = $1
"""


class UserRepo:
    """Structurally satisfies `service.protocols.UserRepository`."""

    def __init__(self, db: Postgres) -> None:
        self._db = db

    async def create(self, user: User) -> None:
        e = UserEntity.from_model(user)
        try:
            await self._db.pool.execute(_INSERT, e.id, e.email, e.password_hash, e.created_at)
        except asyncpg.UniqueViolationError as exc:
            raise EmailAlreadyExists() from exc

    async def get_by_email(self, email: str) -> User:
        record = await self._db.pool.fetchrow(_GET_BY_EMAIL, email)
        if record is None:
            raise UserNotFound()
        return UserEntity.from_record(record).to_model()
