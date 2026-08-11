"""Observability ports."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LoggerPort(Protocol):
    def bind(self, **context: Any) -> LoggerPort: ...

    def debug(self, message: str, **fields: Any) -> None: ...

    def info(self, message: str, **fields: Any) -> None: ...

    def warning(self, message: str, **fields: Any) -> None: ...

    def error(self, message: str, **fields: Any) -> None: ...

    def exception(self, message: str, **fields: Any) -> None: ...


@runtime_checkable
class MetricsPort(Protocol):
    def counter(
        self, name: str, value: float = 1.0, *, tags: Mapping[str, str] | None = None
    ) -> None: ...

    def gauge(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None: ...

    def histogram(
        self, name: str, value: float, *, tags: Mapping[str, str] | None = None
    ) -> None: ...


@runtime_checkable
class TracerPort(Protocol):
    def start_span(
        self,
        name: str,
        *,
        attributes: Mapping[str, str | int | float | bool] | None = None,
    ) -> AbstractAsyncContextManager[Any]: ...
