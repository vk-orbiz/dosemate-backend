"""Auth business logic. Depends on Protocols only (rule 2).

Passwords are stored as PBKDF2-HMAC-SHA256 with a per-user random salt, in the
self-describing form `pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>`, so the
iteration count can be raised later without invalidating existing hashes.
"""

import asyncio
import base64
import hashlib
import hmac
import os
from datetime import UTC, datetime
from uuid import uuid4

from app.core.errors import InvalidCredentials, UserNotFound
from app.models.user import Credentials, Session, Signup, User
from app.service.jwt import JWTService
from app.service.protocols import UserRepository

DEFAULT_HASH_ITERATIONS = 600_000
_SCHEME = "pbkdf2_sha256"
_SALT_LEN = 16


def hash_password(password: str, iterations: int) -> str:
    salt = os.urandom(_SALT_LEN)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    b64 = base64.b64encode
    return f"{_SCHEME}${iterations}${b64(salt).decode()}${b64(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = encoded.split("$")
        if scheme != _SCHEME:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)


class AuthService:
    def __init__(
        self,
        users: UserRepository,
        jwt: JWTService,
        *,
        hash_iterations: int = DEFAULT_HASH_ITERATIONS,
    ) -> None:
        self._users = users
        self._jwt = jwt
        self._iterations = hash_iterations
        # Verified against when the email is unknown so timing doesn't reveal existence.
        self._dummy_hash = hash_password(os.urandom(16).hex(), hash_iterations)

    async def signup(self, signup: Signup) -> User:
        """Raises EmailAlreadyExists."""
        user = User(
            id=uuid4(),
            email=signup.email,
            password_hash=await asyncio.to_thread(hash_password, signup.password, self._iterations),
            created_at=datetime.now(UTC),
        )
        await self._users.create(user)
        return user

    async def login(self, credentials: Credentials) -> Session:
        """Raises InvalidCredentials for both unknown email and wrong password."""
        try:
            user = await self._users.get_by_email(credentials.email)
        except UserNotFound:
            await asyncio.to_thread(verify_password, credentials.password, self._dummy_hash)
            raise InvalidCredentials() from None

        if not await asyncio.to_thread(verify_password, credentials.password, user.password_hash):
            raise InvalidCredentials()

        return Session(
            access_token=self._jwt.issue(user.id),
            expires_in=self._jwt.ttl_seconds,
            user_id=user.id,
        )
