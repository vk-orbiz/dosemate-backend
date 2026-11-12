"""Access-token issuing and verification."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.errors import InvalidToken

_ALGORITHM = "HS256"


class JWTService:
    def __init__(self, secret: str, ttl_seconds: int) -> None:
        self._secret = secret
        self._ttl_seconds = ttl_seconds

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    def issue(self, user_id: UUID) -> str:
        now = datetime.now(UTC)
        claims = {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(seconds=self._ttl_seconds),
        }
        return jwt.encode(claims, self._secret, algorithm=_ALGORITHM)

    def verify(self, token: str) -> UUID:
        """Return the user id in `token`. Raises InvalidToken."""
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[_ALGORITHM],
                options={"require": ["exp", "sub"]},
            )
            return UUID(claims["sub"])
        except (jwt.PyJWTError, ValueError, TypeError) as exc:
            raise InvalidToken() from exc
