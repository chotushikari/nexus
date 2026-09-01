"""Structured (JSON-line) logging for the NEXUS backend.

Every log record carries a stable `event` key so logs can be grepped/queried
without parsing prose. `get_logger(__name__).info("store.selected", backend=...)`
produces one JSON object per line on stderr.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

_CONFIGURED = False

_RESERVED = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "taskName",
    "thread",
    "threadName",
}


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            payload[key] = _coerce(value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _coerce(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_coerce(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _coerce(v) for k, v in value.items()}
    return str(value)


def configure_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonLineFormatter())
    root = logging.getLogger("nexus")
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.propagate = False
    _CONFIGURED = True


class StructuredLogger:
    """Thin adapter so callers can pass structured fields as kwargs."""

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(f"nexus.{name}")

    def _log(self, level: int, event: str, exc_info: bool = False, **fields: Any) -> None:
        self._logger.log(level, event, extra=fields, exc_info=exc_info)

    def debug(self, event: str, **fields: Any) -> None:
        self._log(logging.DEBUG, event, **fields)

    def info(self, event: str, **fields: Any) -> None:
        self._log(logging.INFO, event, **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self._log(logging.WARNING, event, **fields)

    def error(self, event: str, exc_info: bool = False, **fields: Any) -> None:
        self._log(logging.ERROR, event, exc_info=exc_info, **fields)


def get_logger(name: str) -> StructuredLogger:
    configure_logging()
    return StructuredLogger(name)
