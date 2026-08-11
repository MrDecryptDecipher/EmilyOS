"""Structured JSON logging for Emily OS."""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from typing import Any, TextIO

import orjson


class StructuredLogger:
    """LoggerPort implementation emitting JSON lines."""

    def __init__(
        self,
        name: str = "emily",
        *,
        level: int = logging.INFO,
        stream: TextIO | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self._name = name
        self._level = level
        self._stream = stream or sys.stderr
        self._context = dict(context or {})

    def bind(self, **context: Any) -> StructuredLogger:
        merged = {**self._context, **context}
        return StructuredLogger(
            self._name,
            level=self._level,
            stream=self._stream,
            context=merged,
        )

    def debug(self, message: str, **fields: Any) -> None:
        self._emit("DEBUG", message, fields)

    def info(self, message: str, **fields: Any) -> None:
        self._emit("INFO", message, fields)

    def warning(self, message: str, **fields: Any) -> None:
        self._emit("WARNING", message, fields)

    def error(self, message: str, **fields: Any) -> None:
        self._emit("ERROR", message, fields)

    def exception(self, message: str, **fields: Any) -> None:
        fields = {**fields, "exc_info": True}
        self._emit("ERROR", message, fields)

    def _emit(self, level: str, message: str, fields: dict[str, Any]) -> None:
        numeric = getattr(logging, level, logging.INFO)
        if numeric < self._level:
            return
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "level": level,
            "logger": self._name,
            "message": message,
            **self._context,
            **{k: v for k, v in fields.items() if k != "exc_info"},
        }
        line = orjson.dumps(record, default=str).decode("utf-8")
        self._stream.write(line + "\n")
        self._stream.flush()


def configure_logging(level: str = "INFO") -> StructuredLogger:
    """Create the root Emily structured logger."""

    numeric = getattr(logging, level.upper(), logging.INFO)
    # Keep stdlib quiet; Emily uses StructuredLogger as the primary facade.
    logging.basicConfig(level=numeric, stream=sys.stderr, force=True)
    return StructuredLogger(level=numeric)
