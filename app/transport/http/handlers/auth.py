"""Thin: validate/convert, call the service, shape the response.

No error handling here: domain errors propagate to the handlers registered in
`server.py`, which use `error_map.py` (rule 4).
"""

from app.transport.http.dto.auth import (
    LoginRequest,
    LoginResponse,
    SignupRequest,
    SignupResponse,
)
from app.transport.http.protocols import AuthSvc
from app.transport.http.validators import auth as validate


class AuthHandler:
    def __init__(self, auth: AuthSvc) -> None:
        self._auth = auth

    async def signup(self, body: SignupRequest) -> SignupResponse:
        user = await self._auth.signup(validate.to_signup(body))
        return SignupResponse(user_id=user.id, email=user.email)

    async def login(self, body: LoginRequest) -> LoginResponse:
        session = await self._auth.login(validate.to_credentials(body))
        return LoginResponse(
            access_token=session.access_token,
            expires_in=session.expires_in,
            user_id=session.user_id,
        )
