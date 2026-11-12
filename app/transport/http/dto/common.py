from typing import Literal

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Documents the error envelope (rule 6) in OpenAPI."""

    message: str
    code: str
    data: object | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
