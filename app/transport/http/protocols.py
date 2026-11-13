"""Ports the HTTP layer needs, defined by the consumer (rule 2).

Handlers and deps depend on these, never on `service/` classes. `main.py` passes in
concrete services that satisfy them structurally.
"""

from typing import Protocol
from uuid import UUID

from app.models.user import Session, User


class AuthSvc(Protocol):
    async def signup(self, email: str, password: str) -> User: ...
    async def login(self, email: str, password: str) -> Session: ...


class JWTSvc(Protocol):
    def verify(self, token: str) -> UUID:
        """Raises InvalidToken."""
        ...
