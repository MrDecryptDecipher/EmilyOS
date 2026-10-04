"""In-process asynchronous event bus."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from emily.core.errors import EventBusError
from emily.core.ids import new_id
from emily.core.protocols.event_bus import EventHandler, EventMiddleware
from emily.events.envelope import EventEnvelope
from emily.events.types import EventTypes

_log = logging.getLogger("emily.events.bus")


@dataclass(slots=True)
class _Subscription:
    subscription_id: str
    pattern: str
    handler: EventHandler


@dataclass
class InProcessEventBus:
    """Async pub/sub bus with prefix matching and middleware."""

    _subscriptions: dict[str, _Subscription] = field(default_factory=dict)
    _middleware: list[EventMiddleware] = field(default_factory=list)
    _started: bool = False
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _pending: set[asyncio.Task[None]] = field(default_factory=set)

    async def start(self) -> None:
        async with self._lock:
            if self._started:
                return
            self._started = True
        await self.publish(EventTypes.BUS_STARTED, {"status": "started"}, source="event_bus")

    async def stop(self) -> None:
        async with self._lock:
            if not self._started:
                return
            self._started = False
        if self._pending:
            await asyncio.gather(*self._pending, return_exceptions=True)
            self._pending.clear()
        # Direct dispatch during shutdown to avoid re-entrancy on stopped flag.
        envelope = EventEnvelope(
            event_type=EventTypes.BUS_STOPPED,
            source="event_bus",
            payload={"status": "stopped"},
        )
        await self._dispatch(envelope)

    def add_middleware(self, middleware: EventMiddleware) -> None:
        self._middleware.append(middleware)

    def subscribe(self, event_type: str, handler: EventHandler) -> str:
        if not event_type:
            raise EventBusError("event_type must be non-empty")
        subscription_id = new_id("sub")
        self._subscriptions[subscription_id] = _Subscription(
            subscription_id=subscription_id,
            pattern=event_type,
            handler=handler,
        )
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> None:
        self._subscriptions.pop(subscription_id, None)

    async def publish(
        self,
        event_type: str,
        payload: Mapping[str, Any] | None = None,
        *,
        source: str = "unknown",
        correlation_id: str | None = None,
        causation_id: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> str:
        if not self._started and event_type not in {
            EventTypes.BUS_STARTED,
            EventTypes.BUS_STOPPED,
        }:
            raise EventBusError(f"event bus not started; cannot publish type={event_type}")

        data: dict[str, object] = {
            "event_type": event_type,
            "source": source,
            "causation_id": causation_id,
            "payload": dict(payload or {}),
            "metadata": dict(metadata or {}),
        }
        if correlation_id is not None:
            data["correlation_id"] = correlation_id
        envelope = EventEnvelope.model_validate(data)

        task = asyncio.create_task(self._dispatch(envelope), name=f"evt:{event_type}")
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)
        return envelope.event_id

    async def _dispatch(self, envelope: EventEnvelope) -> None:
        handlers = [
            sub.handler
            for sub in self._subscriptions.values()
            if self._matches(sub.pattern, envelope.event_type)
        ]
        if not handlers:
            return

        async def terminal(event_type: str, payload: Mapping[str, Any]) -> None:
            await asyncio.gather(
                *(self._safe_call(handler, event_type, payload) for handler in handlers)
            )

        chain = terminal
        for middleware in reversed(self._middleware):

            def wrap(
                mw: EventMiddleware,
                nxt: Any,
            ) -> Any:
                async def _inner(event_type: str, payload: Mapping[str, Any]) -> None:
                    await mw(event_type, payload, nxt)

                return _inner

            chain = wrap(middleware, chain)

        await chain(envelope.event_type, envelope.payload)

    @staticmethod
    async def _safe_call(
        handler: EventHandler,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> None:
        try:
            await handler(event_type, payload)
        except Exception:
            _log.exception("event handler failed type=%s", event_type)

    @staticmethod
    def _matches(pattern: str, event_type: str) -> bool:
        if pattern == "*" or pattern == event_type:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return event_type == prefix or event_type.startswith(prefix + ".")
        if pattern.endswith("*"):
            return event_type.startswith(pattern[:-1])
        return False
