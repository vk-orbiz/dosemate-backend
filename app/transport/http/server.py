"""HTTP app factory: FastAPI instance, routers, middleware, exception handlers.

Knows nothing about services or repos; `main.py` attaches those to `app.state`.
"""

from dataclasses import asdict
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.types import Lifespan

from app.core.config import Settings
from app.core.errors import DomainError
from app.models.error import ErrorBody
from app.transport.http.error_map import to_http_error
from app.transport.http.middleware import add_middlewares
from app.transport.http.routes import auth, general

# Starlette's handler signature takes `Exception`, so each handler narrows its argument.


def _json(status: int, body: ErrorBody) -> JSONResponse:
    return JSONResponse(status_code=status, content=asdict(body))


async def _domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    status, body = to_http_error(exc)
    return _json(status, body)


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = [
        {"field": ".".join(str(p) for p in err["loc"][1:]), "message": err["msg"]}
        for err in exc.errors()
    ]
    return _json(422, ErrorBody(message="Invalid request", code="invalid_input", data=details))


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    if exc.status_code == 404:
        return await general.not_found_handler(request, exc)
    phrase = HTTPStatus(exc.status_code).phrase
    body = ErrorBody(message=str(exc.detail), code=phrase.lower().replace(" ", "_"))
    return _json(exc.status_code, body)


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request.app.state.logger.exception("unhandled error", path=request.url.path)
    return _json(500, ErrorBody(message="Internal server error", code="internal_error"))


def create_app(settings: Settings, lifespan: Lifespan[FastAPI]) -> FastAPI:
    is_prod = settings.env == "production"
    app = FastAPI(
        title="DoseMate API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,  # Swagger replaced by Scalar (general.docs_router)
        redoc_url=None,
        openapi_url=None if is_prod else "/openapi.json",
    )
    add_middlewares(app, settings)

    app.include_router(general.router)
    if not is_prod:
        app.include_router(general.docs_router)
    app.include_router(auth.router)

    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
    return app
