"""AuthService and JWTService against an in-memory fake repo (no database, no HTTP)."""

import time
from uuid import UUID

import pytest

from app.core.errors import EmailAlreadyExists, InvalidCredentials, InvalidToken, UserNotFound
from app.models.user import User
from app.service.auth import AuthService, verify_password
from app.service.jwt import JWTService

SECRET = "unit-test-secret-0123456789abcdef-xyz"


class FakeUserRepo:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}

    async def create(self, user: User) -> None:
        if user.email in self.users:
            raise EmailAlreadyExists()
        self.users[user.email] = user

    async def get_by_email(self, email: str) -> User:
        if email not in self.users:
            raise UserNotFound()
        return self.users[email]


@pytest.fixture
def repo() -> FakeUserRepo:
    return FakeUserRepo()


@pytest.fixture
def jwt_service() -> JWTService:
    return JWTService(SECRET, ttl_seconds=60)


@pytest.fixture
def service(repo: FakeUserRepo, jwt_service: JWTService) -> AuthService:
    return AuthService(repo, jwt_service, hash_iterations=1_000)  # fast for tests


EMAIL = "alice@example.com"
PASSWORD = "correct horse battery"


async def test_signup_stores_hash_not_plaintext(service: AuthService, repo: FakeUserRepo) -> None:
    user = await service.signup(EMAIL, PASSWORD)

    assert repo.users["alice@example.com"] == user
    assert "correct horse battery" not in user.password_hash
    assert user.password_hash.startswith("pbkdf2_sha256$1000$")
    assert verify_password("correct horse battery", user.password_hash)
    assert not verify_password("wrong", user.password_hash)


async def test_same_password_gets_different_hashes(service: AuthService) -> None:
    a = await service.signup(EMAIL, PASSWORD)
    b = await service.signup("bob@example.com", PASSWORD)
    assert a.password_hash != b.password_hash


async def test_signup_duplicate_email(service: AuthService) -> None:
    await service.signup(EMAIL, PASSWORD)
    with pytest.raises(EmailAlreadyExists):
        await service.signup(EMAIL, PASSWORD)


async def test_login_success(service: AuthService, jwt_service: JWTService) -> None:
    user = await service.signup(EMAIL, PASSWORD)

    session = await service.login(EMAIL, PASSWORD)

    assert session.user_id == user.id
    assert session.expires_in == 60
    assert jwt_service.verify(session.access_token) == user.id


async def test_login_wrong_password(service: AuthService) -> None:
    await service.signup(EMAIL, PASSWORD)
    with pytest.raises(InvalidCredentials):
        await service.login(EMAIL, "nope nope nope")


async def test_login_unknown_email(service: AuthService) -> None:
    with pytest.raises(InvalidCredentials):
        await service.login("nobody@example.com", PASSWORD)


def test_verify_password_tolerates_malformed_hash() -> None:
    assert not verify_password("x", "garbage")
    assert not verify_password("x", "md5$1$a$b")


def test_jwt_rejects_garbage(jwt_service: JWTService) -> None:
    with pytest.raises(InvalidToken):
        jwt_service.verify("not-a-token")


def test_jwt_rejects_wrong_signature(jwt_service: JWTService) -> None:
    token = JWTService("another-secret-0123456789abcdef-xyz", 60).issue(UUID(int=1))
    with pytest.raises(InvalidToken):
        jwt_service.verify(token)


def test_jwt_rejects_expired() -> None:
    svc = JWTService(SECRET, ttl_seconds=-1)
    token = svc.issue(UUID(int=1))
    time.sleep(0.01)
    with pytest.raises(InvalidToken):
        svc.verify(token)
