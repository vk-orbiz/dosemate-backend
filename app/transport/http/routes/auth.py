from fastapi import APIRouter

from app.models.error import ErrorBody
from app.transport.http.deps import AuthSvcDep
from app.transport.http.dto.auth import (
    LoginRequest,
    LoginResponse,
    SignupRequest,
    SignupResponse,
)
from app.transport.http.dto.common import Envelope, ok

router = APIRouter(
    prefix="/v1/auth",
    tags=["auth"],
    responses={422: {"model": ErrorBody}},
)


@router.post(
    "/signup",
    status_code=201,
    response_model=Envelope[SignupResponse],
    responses={409: {"model": ErrorBody}},
)
async def signup(body: SignupRequest, auth: AuthSvcDep) -> Envelope[SignupResponse]:
    user = await auth.signup(body.email, body.password)
    return ok(SignupResponse(user_id=user.id, email=user.email), "Account created")


@router.post(
    "/login",
    response_model=Envelope[LoginResponse],
    responses={401: {"model": ErrorBody}},
)
async def login(body: LoginRequest, auth: AuthSvcDep) -> Envelope[LoginResponse]:
    session = await auth.login(body.email, body.password)
    return ok(
        LoginResponse(
            access_token=session.access_token,
            expires_in=session.expires_in,
            user_id=session.user_id,
        )
    )
