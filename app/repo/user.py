"""Data access for users. Returns domain models, raises domain errors (rules 3, 4, 7)."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import EmailAlreadyExists, UserNotFound
from app.models.user import User
from app.storage.postgres.models import UserRow

_UNIQUE_VIOLATION = "23505"


class UserRepo:
    """Structurally satisfies `service.protocols.UserRepository`."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def create(self, user: User) -> None:
        try:
            async with self._sessions.begin() as session:
                session.add(UserRow(**user.model_dump()))
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == _UNIQUE_VIOLATION:
                raise EmailAlreadyExists() from exc
            raise

    async def get_by_email(self, email: str) -> User:
        async with self._sessions() as session:
            row = await session.scalar(select(UserRow).where(UserRow.email == email))
        if row is None:
            raise UserNotFound()
        return User.model_validate(row)
