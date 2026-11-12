"""Row shape for the users table. Entities never leave `repo/` (rule 3)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Self
from uuid import UUID

import asyncpg

from app.models.user import User


@dataclass(frozen=True, slots=True)
class UserEntity:
    id: UUID
    email: str
    password_hash: str
    created_at: datetime

    @classmethod
    def from_record(cls, record: asyncpg.Record) -> Self:
        return cls(
            id=record["id"],
            email=record["email"],
            password_hash=record["password_hash"],
            created_at=record["created_at"],
        )

    @classmethod
    def from_model(cls, user: User) -> Self:
        return cls(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            created_at=user.created_at,
        )

    def to_model(self) -> User:
        return User(
            id=self.id,
            email=self.email,
            password_hash=self.password_hash,
            created_at=self.created_at,
        )
