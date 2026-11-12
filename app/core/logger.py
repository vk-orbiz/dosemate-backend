"""Logger port + console adapter. Layers depend on the `Logger` Protocol, not on `logging`."""

import logging
import sys
from typing import Protocol


class Logger(Protocol):
    def debug(self, msg: str, **fields: object) -> None: ...
    def info(self, msg: str, **fields: object) -> None: ...
    def warning(self, msg: str, **fields: object) -> None: ...
    def error(self, msg: str, **fields: object) -> None: ...
    def exception(self, msg: str, **fields: object) -> None:
        """Log at ERROR level including the exception currently being handled."""
        ...


class ConsoleLogger:
    """Writes `time level message key=value ...` lines to stdout."""

    def __init__(self, level: str = "INFO", name: str = "dosemate") -> None:
        self._log = logging.getLogger(name)
        self._log.setLevel(level)
        self._log.propagate = False
        self._log.handlers.clear()  # building twice (e.g. in tests) must not duplicate output
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self._log.addHandler(handler)

    @staticmethod
    def _fmt(msg: str, fields: dict[str, object]) -> str:
        if not fields:
            return msg
        return f"{msg} " + " ".join(f"{k}={v!r}" for k, v in fields.items())

    def debug(self, msg: str, **fields: object) -> None:
        self._log.debug(self._fmt(msg, fields))

    def info(self, msg: str, **fields: object) -> None:
        self._log.info(self._fmt(msg, fields))

    def warning(self, msg: str, **fields: object) -> None:
        self._log.warning(self._fmt(msg, fields))

    def error(self, msg: str, **fields: object) -> None:
        self._log.error(self._fmt(msg, fields))

    def exception(self, msg: str, **fields: object) -> None:
        self._log.exception(self._fmt(msg, fields))
