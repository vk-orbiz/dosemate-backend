"""Ports the service layer needs, defined by the consumer (rule 2).

`repo/` implements these structurally; the service never imports `repo`, `storage`
or `transport`. Implementations raise the domain errors documented on each method.
"""

from typing import Protocol

from app.models.user import User


class UserRepository(Protocol):
    async def create(self, user: User) -> None:
        """Raises EmailAlreadyExists."""
        ...

    async def get_by_email(self, email: str) -> User:
        """Raises UserNotFound."""
        ...
