from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ErrorBody:
    """The single error envelope used by every error response (rule 6)."""

    message: str
    code: str
    data: object | None = None
