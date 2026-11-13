from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from scalar_fastapi import get_scalar_api_reference
from starlette.exceptions import HTTPException

from app.models.error import ErrorBody
from app.transport.http.dto.common import Envelope, HealthResponse, ok

router = APIRouter(prefix="/v1", tags=["general"])
docs_router = APIRouter(include_in_schema=False)  # registered only outside production


@router.get("/health", response_model=Envelope[HealthResponse])
async def health() -> Envelope[HealthResponse]:
    return ok(HealthResponse(status="ok"))


async def not_found_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """404 fallback in the standard error envelope."""
    body = ErrorBody(message="Route not found", code="not_found")
    return JSONResponse(status_code=404, content=body.model_dump())


@docs_router.get("/docs", response_class=HTMLResponse)
async def scalar_docs(request: Request) -> HTMLResponse:
    """Scalar API reference, rendered from the app's OpenAPI document."""
    return get_scalar_api_reference(
        openapi_url=request.app.openapi_url,
        title=request.app.title,
    )
