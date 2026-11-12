"""Pure domain objects: no framework or database imports."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    email: str
    password_hash: str  # self-describing encoded hash; never the plaintext password
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Signup:
    """Validated signup input, as handed to the service."""

    email: str
    password: str


@dataclass(frozen=True, slots=True)
class Credentials:
    email: str
    password: str


@dataclass(frozen=True, slots=True)
class Session:
    """Result of a successful login."""

    access_token: str
    expires_in: int  # seconds
    user_id: UUID
