from fastapi import APIRouter

from app.transport.http.deps import AuthHandlerDep
from app.transport.http.dto.auth import (
    LoginRequest,
    LoginResponse,
    SignupRequest,
    SignupResponse,
)
from app.transport.http.dto.common import ErrorResponse

router = APIRouter(
    prefix="/v1/auth",
    tags=["auth"],
    responses={422: {"model": ErrorResponse}},
)


@router.post(
    "/signup",
    status_code=201,
    response_model=SignupResponse,
    responses={409: {"model": ErrorResponse}},
)
async def signup(body: SignupRequest, handler: AuthHandlerDep) -> SignupResponse:
    return await handler.signup(body)


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={401: {"model": ErrorResponse}},
)
async def login(body: LoginRequest, handler: AuthHandlerDep) -> LoginResponse:
    return await handler.login(body)
