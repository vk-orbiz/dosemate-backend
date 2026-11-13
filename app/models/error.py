from pydantic import BaseModel, ConfigDict


class ErrorBody(BaseModel):
    """The single error envelope used by every error response (rule 6).

    Also the OpenAPI schema for error responses.
    """

    model_config = ConfigDict(frozen=True)

    message: str
    code: str
    data: object | None = None
