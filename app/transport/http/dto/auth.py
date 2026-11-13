"""Request/response schemas. Requests carry ALL input validation (shape, size, format,
password policy) and normalisation; failures surface as 422 `invalid_input` via
`server._validation_error_handler`. Business rules belong in `service/`, not here."""

from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, EmailStr, Field

MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 128


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


# One account per address regardless of case, so the stored form is trimmed and lower-case.
NormalizedEmail = Annotated[EmailStr, BeforeValidator(_strip), AfterValidator(str.lower)]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SignupRequest(_Request):
    email: NormalizedEmail
    password: Annotated[str, Field(min_length=MIN_PASSWORD_LEN, max_length=MAX_PASSWORD_LEN)]


class SignupResponse(BaseModel):
    user_id: UUID
    email: str


class LoginRequest(_Request):
    email: NormalizedEmail
    # Login only needs to be non-empty; the policy applies when the password is chosen.
    password: Annotated[str, Field(min_length=1, max_length=MAX_PASSWORD_LEN)]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: UUID
