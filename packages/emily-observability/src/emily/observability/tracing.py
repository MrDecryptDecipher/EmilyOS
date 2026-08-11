"""No-op async tracer for M0 (OTel in M10)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager


class _Span:
    def __init__(
        self, name: str, attributes: Mapping[str, str | int | float | bool] | None
    ) -> None:
        self.name = name
        self.attributes = dict(attributes or {})


class NoOpTracer:
    @asynccontextmanager
    async def start_span(
        self,
        name: str,
        *,
        attributes: Mapping[str, str | int | float | bool] | None = None,
    ) -> AsyncIterator[_Span]:
        yield _Span(name, attributes)
