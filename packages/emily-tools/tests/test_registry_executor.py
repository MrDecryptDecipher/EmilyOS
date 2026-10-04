"""Tool registry, builtins, policy, and executor tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from emily.core.types.tool import ToolPermissionLevel
from emily.events.bus import InProcessEventBus
from emily.tools.builtins import register_builtins
from emily.tools.executor import ToolExecutor
from emily.tools.models import CapabilityToken, ToolInvocation, ToolSource, ToolSpec
from emily.tools.policy import PermissionPolicy
from emily.tools.registry import ToolRegistry
from emily.tools.runtime import ToolRuntime


@pytest.mark.asyncio
async def test_builtins_echo_math_text_clock(tmp_path: Path) -> None:
    runtime = ToolRuntime(mcp_catalog_path=tmp_path / "catalog.json")
    await runtime.start()
    echo = await runtime.invoke("echo", {"message": "hi"})
    assert echo.success and echo.output["message"] == "hi"
    math = await runtime.invoke("math.eval", {"expression": "(2+3)*4"})
    assert math.success and math.output["value"] == 20
    stats = await runtime.invoke("text.stats", {"text": "one two\nthree"})
    assert stats.success and stats.output["words"] == 3
    clock = await runtime.invoke("clock.now", {})
    assert clock.success and "iso" in clock.output
    await runtime.stop()


@pytest.mark.asyncio
async def test_policy_denies_network_without_setting() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="net.ping",
            title="Net",
            permissions=[ToolPermissionLevel.NETWORK],
            source=ToolSource.BUILTIN,
        ),
        _ok,
    )
    executor = ToolExecutor(registry, PermissionPolicy(settings=type("S", (), {"allow_network": False})()))
    result = await executor.invoke(ToolInvocation(tool_name="net.ping"))
    assert result.denied is True
    assert result.success is False


@pytest.mark.asyncio
async def test_capability_token_restricts_and_expires() -> None:
    registry = ToolRegistry()
    register_builtins(registry)
    executor = ToolExecutor(registry, PermissionPolicy())
    denied = await executor.invoke(
        ToolInvocation(
            tool_name="math.eval",
            arguments={"expression": "1+1"},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.READ]),
        )
    )
    assert denied.denied is True

    expired = await executor.invoke(
        ToolInvocation(
            tool_name="echo",
            arguments={"message": "x"},
            capabilities=CapabilityToken(
                granted=[ToolPermissionLevel.READ],
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            ),
        )
    )
    assert expired.denied is True
    assert "expired" in (expired.error or "")

    ok = await executor.invoke(
        ToolInvocation(
            tool_name="echo",
            arguments={"message": "x"},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.READ]),
        )
    )
    assert ok.success is True


@pytest.mark.asyncio
async def test_executor_events_and_timeout(tmp_path: Path) -> None:
    bus = InProcessEventBus()
    await bus.start()
    seen: list[str] = []

    async def capture(event_type: str, _payload: dict[str, object]) -> None:
        seen.append(event_type)

    bus.subscribe("tool.*", capture)
    registry = ToolRegistry()

    async def slow(_args):  # type: ignore[no-untyped-def]
        import asyncio

        await asyncio.sleep(0.2)
        return {"ok": True}

    registry.register(
        ToolSpec(name="slow", title="Slow", permissions=[ToolPermissionLevel.READ]),
        slow,
    )
    executor = ToolExecutor(registry, event_bus=bus, default_timeout_seconds=0.05)
    result = await executor.invoke(ToolInvocation(tool_name="slow"))
    assert result.success is False
    assert "timed out" in (result.error or "")
    await bus.stop()
    assert "tool.failed" in seen


async def _ok(_arguments):  # type: ignore[no-untyped-def]
    return {"ok": True}


@pytest.mark.asyncio
async def test_math_rejects_unsafe_expression(tmp_path: Path) -> None:
    runtime = ToolRuntime(mcp_catalog_path=tmp_path / "c.json")
    await runtime.start()
    bad = await runtime.invoke("math.eval", {"expression": "__import__('os').system('x')"})
    assert bad.success is False
    await runtime.stop()
