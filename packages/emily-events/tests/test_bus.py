"""Event bus unit tests."""

from __future__ import annotations

import asyncio

import pytest

from emily.core.errors import EventBusError
from emily.events.bus import InProcessEventBus
from emily.events.types import EventTypes


@pytest.mark.asyncio
async def test_publish_requires_start() -> None:
    bus = InProcessEventBus()
    with pytest.raises(EventBusError):
        await bus.publish("demo.event", {"a": 1})


@pytest.mark.asyncio
async def test_subscribe_and_receive() -> None:
    bus = InProcessEventBus()
    received: list[tuple[str, dict[str, object]]] = []

    async def handler(event_type: str, payload: dict[str, object]) -> None:
        received.append((event_type, dict(payload)))

    await bus.start()
    bus.subscribe("demo.*", handler)
    await bus.publish("demo.created", {"id": 1}, source="test")
    await asyncio.sleep(0.05)
    await bus.stop()

    assert any(item[0] == "demo.created" for item in received)


@pytest.mark.asyncio
async def test_handler_failure_isolated() -> None:
    bus = InProcessEventBus()
    ok: list[str] = []

    async def bad(_event_type: str, _payload: dict[str, object]) -> None:
        raise RuntimeError("boom")

    async def good(event_type: str, _payload: dict[str, object]) -> None:
        ok.append(event_type)

    await bus.start()
    bus.subscribe("x.y", bad)
    bus.subscribe("x.y", good)
    await bus.publish("x.y", {})
    await asyncio.sleep(0.05)
    await bus.stop()
    assert ok == ["x.y"]


@pytest.mark.asyncio
async def test_middleware_runs() -> None:
    bus = InProcessEventBus()
    trail: list[str] = []

    async def mw(
        event_type: str,
        payload: dict[str, object],
        next_handler: object,
    ) -> None:
        trail.append("before")
        await next_handler(event_type, payload)  # type: ignore[operator]
        trail.append("after")

    async def handler(_event_type: str, _payload: dict[str, object]) -> None:
        trail.append("handler")

    await bus.start()
    bus.add_middleware(mw)
    bus.subscribe("mw.test", handler)
    await bus.publish("mw.test", {})
    await asyncio.sleep(0.05)
    await bus.stop()
    assert trail == ["before", "handler", "after"]


@pytest.mark.asyncio
async def test_bus_lifecycle_events_exist() -> None:
    assert EventTypes.BUS_STARTED.startswith("events.")
