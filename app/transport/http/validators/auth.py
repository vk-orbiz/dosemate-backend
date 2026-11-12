"""DTO -> domain model conversion plus semantic validation.

Pydantic already checked shape and size; this checks meaning (valid email, password
policy) and raises `InvalidInput`, which the error map turns into a 422.
"""

from email_validator import EmailNotValidError, validate_email

from app.core.errors import InvalidInput
from app.models.user import Credentials, Signup
from app.transport.http.dto.auth import LoginRequest, SignupRequest

MIN_PASSWORD_LEN = 8


def validate_email_address(raw: str) -> str:
    try:
        result = validate_email(raw.strip(), check_deliverability=False)
    except EmailNotValidError as exc:
        raise InvalidInput(f"invalid email: {exc}") from exc
    return result.normalized.lower()  # one account per address, regardless of case


def to_signup(dto: SignupRequest) -> Signup:
    if len(dto.password) < MIN_PASSWORD_LEN:
        raise InvalidInput(f"password must be at least {MIN_PASSWORD_LEN} characters")
    return Signup(email=validate_email_address(dto.email), password=dto.password)


def to_credentials(dto: LoginRequest) -> Credentials:
    return Credentials(email=validate_email_address(dto.email), password=dto.password)
