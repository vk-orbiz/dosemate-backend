import pytest

from app.core.errors import InvalidInput
from app.transport.http.dto.auth import SignupRequest
from app.transport.http.validators.auth import to_signup


def test_to_signup_normalises_email() -> None:
    signup = to_signup(SignupRequest(email=" Alice@Example.COM ", password="long enough pw"))
    assert signup.email == "alice@example.com"


@pytest.mark.parametrize(
    ("email", "password"),
    [("not-an-email", "long enough pw"), ("a@example.com", "short")],
)
def test_to_signup_rejects_bad_input(email: str, password: str) -> None:
    with pytest.raises(InvalidInput):
        to_signup(SignupRequest(email=email, password=password))
