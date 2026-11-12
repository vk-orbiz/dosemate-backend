"""Domain exception hierarchy. No HTTP knowledge here: status codes live in
`transport/http/error_map.py` only (rule 4). Repos and services raise these."""


class DomainError(Exception):
    """Base for every error the application raises on purpose."""

    def __init__(self, message: str | None = None, *, data: object | None = None) -> None:
        super().__init__(message or type(self).__name__)
        self.message = message
        self.data = data


class InvalidInput(DomainError):
    """Input is well-formed but semantically unacceptable."""


class NotFound(DomainError):
    """A requested entity does not exist."""


class UserNotFound(NotFound):
    pass


class EmailAlreadyExists(DomainError):
    pass


class InvalidCredentials(DomainError):
    """Unknown email or wrong auth key; deliberately indistinguishable."""


class InvalidToken(DomainError):
    """Access token missing, malformed, expired or badly signed."""
