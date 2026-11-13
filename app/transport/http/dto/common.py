from typing import Literal

from pydantic import BaseModel


class Envelope[T](BaseModel):
    """The shape of EVERY successful response: `{"message", "code", "data"}`.

    Same keys as the error envelope (`ErrorBody`), so clients parse one shape; the HTTP status
    says which one they got. `data` is the endpoint's own payload (any response DTO).
    """

    message: str = "OK"
    code: str = "ok"
    data: T


def ok[T](data: T, message: str = "OK") -> Envelope[T]:
    return Envelope(message=message, code="ok", data=data)


class HealthResponse(BaseModel):
    status: Literal["ok"]
