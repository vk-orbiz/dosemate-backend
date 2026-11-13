"""FastAPI `Depends` providers. Objects are built in `main.py` and stored on
`app.state` (rule 5); nothing here constructs or caches anything itself."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import InvalidToken
from app.transport.http.protocols import AuthSvc, JWTSvc

_bearer = HTTPBearer(auto_error=False)


def get_auth_svc(request: Request) -> AuthSvc:
    svc: AuthSvc = request.app.state.auth_service
    return svc


def get_jwt_svc(request: Request) -> JWTSvc:
    svc: JWTSvc = request.app.state.jwt_service
    return svc


def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    jwt_svc: Annotated[JWTSvc, Depends(get_jwt_svc)],
) -> UUID:
    """Dependency for protected routes (none yet): the authenticated user's id."""
    if credentials is None:
        raise InvalidToken("missing bearer token")
    return jwt_svc.verify(credentials.credentials)


AuthSvcDep = Annotated[AuthSvc, Depends(get_auth_svc)]
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
