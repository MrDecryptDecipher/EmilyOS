"""Event bus port definitions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EventHandler(Protocol):
    async def __call__(self, event_type: str, payload: Mapping[str, Any]) -> None: ...


@runtime_checkable
class EventMiddleware(Protocol):
    async def __call__(
        self,
        event_type: str,
        payload: Mapping[str, Any],
        next_handler: Callable[[str, Mapping[str, Any]], Awaitable[None]],
    ) -> None: ...


@runtime_checkable
class EventBusPort(Protocol):
    async def publish(
        self,
        event_type: str,
        payload: Mapping[str, Any] | None = None,
        *,
        source: str = "unknown",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> str: ...

    def subscribe(self, event_type: str, handler: EventHandler) -> str: ...

    def unsubscribe(self, subscription_id: str) -> None: ...

    def add_middleware(self, middleware: EventMiddleware) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...
