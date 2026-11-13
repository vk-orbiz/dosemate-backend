"""Request DTOs are the validation layer: shape, size, email format/normalisation, policy."""

import pytest
from pydantic import ValidationError

from app.transport.http.dto.auth import LoginRequest, SignupRequest


def test_signup_normalises_email() -> None:
    dto = SignupRequest(email=" Alice@Example.COM ", password="long enough pw")
    assert dto.email == "alice@example.com"


def test_login_normalises_email() -> None:
    assert LoginRequest(email=" Bob@Example.COM ", password="x").email == "bob@example.com"


@pytest.mark.parametrize(
    ("email", "password", "field"),
    [
        ("not-an-email", "long enough pw", "email"),
        ("", "long enough pw", "email"),
        ("a@example.com", "short", "password"),
        ("a@example.com", "x" * 129, "password"),
    ],
)
def test_signup_rejects_bad_input(email: str, password: str, field: str) -> None:
    with pytest.raises(ValidationError) as exc:
        SignupRequest(email=email, password=password)
    assert {err["loc"][0] for err in exc.value.errors()} == {field}


def test_login_rejects_bad_email_and_empty_password() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(email="nope", password="x")
    with pytest.raises(ValidationError):
        LoginRequest(email="a@example.com", password="")


def test_requests_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SignupRequest.model_validate(
            {"email": "a@example.com", "password": "long enough pw", "admin": True}
        )
