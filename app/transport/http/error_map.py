"""The ONLY place domain errors become HTTP status codes and error codes (rule 4)."""

from typing import NamedTuple

from app.core.errors import (
    DomainError,
    EmailAlreadyExists,
    InvalidCredentials,
    InvalidInput,
    InvalidToken,
    NotFound,
)
from app.models.error import ErrorBody


class ErrorSpec(NamedTuple):
    status: int
    code: str
    message: str  # default, used when the exception carries no message of its own


_INTERNAL = ErrorSpec(500, "internal_error", "Internal server error")

_ERROR_MAP: dict[type[DomainError], ErrorSpec] = {
    InvalidInput: ErrorSpec(422, "invalid_input", "Invalid input"),
    EmailAlreadyExists: ErrorSpec(409, "email_taken", "Email is already registered"),
    InvalidCredentials: ErrorSpec(401, "invalid_credentials", "Invalid email or credentials"),
    InvalidToken: ErrorSpec(401, "invalid_token", "Invalid or missing access token"),
    NotFound: ErrorSpec(404, "not_found", "Resource not found"),
}


def to_http_error(exc: DomainError) -> tuple[int, ErrorBody]:
    """Resolve by walking the exception's MRO, so subclasses inherit their parent's mapping."""
    spec = next((_ERROR_MAP[c] for c in type(exc).__mro__ if c in _ERROR_MAP), _INTERNAL)
    # Never expose custom messages on server errors.
    message = exc.message if exc.message and spec.status < 500 else spec.message
    return spec.status, ErrorBody(message=message, code=spec.code, data=exc.data)
