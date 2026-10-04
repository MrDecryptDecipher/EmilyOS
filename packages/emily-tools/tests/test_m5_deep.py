"""Deep unit coverage for M5 tools policy, registry, executor edges."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from emily.core.types.tool import ToolPermissionLevel
from emily.events.bus import InProcessEventBus
from emily.tools.errors import ToolNotFoundError
from emily.tools.executor import ToolExecutor
from emily.tools.models import ToolInvocation, ToolSource, ToolSpec
from emily.tools.policy import PermissionPolicy
from emily.tools.registry import ToolRegistry
from emily.tools.runtime import ToolRuntime


def test_policy_matrix_from_settings() -> None:
    locked = PermissionPolicy(
        SimpleNamespace(
            allow_file_write=False,
            allow_terminal=False,
            allow_system_commands=False,
            allow_network=False,
            desktop_control=False,
            allow_browser=False,
            browser_automation=False,
            tool_allow_execute=False,
        )
    )
    assert locked.allowed_levels() == frozenset({ToolPermissionLevel.READ})

    open_policy = PermissionPolicy(
        SimpleNamespace(
            allow_file_write=True,
            allow_terminal=True,
            allow_system_commands=True,
            allow_network=True,
            desktop_control=True,
            allow_browser=True,
            browser_automation=False,
            tool_allow_execute=True,
        )
    )
    levels = open_policy.allowed_levels()
    assert ToolPermissionLevel.WRITE in levels
    assert ToolPermissionLevel.EXECUTE in levels
    assert ToolPermissionLevel.NETWORK in levels
    assert ToolPermissionLevel.DESKTOP in levels
    assert ToolPermissionLevel.BROWSER in levels
    assert ToolPermissionLevel.PRIVILEGED in levels


@pytest.mark.asyncio
async def test_disabled_tool_and_not_found(tmp_path: Path) -> None:
    runtime = ToolRuntime(mcp_catalog_path=tmp_path / "c.json")
    await runtime.start()
    tool = runtime.registry.get("echo")
    tool.spec.enabled = False
    denied = await runtime.invoke("echo", {"message": "x"})
    assert denied.denied is True
    assert denied.error == "tool disabled"
    with pytest.raises(ToolNotFoundError):
        runtime.registry.get("no.such.tool")
    await runtime.stop()


@pytest.mark.asyncio
async def test_registry_unregister_and_clear_source(tmp_path: Path) -> None:
    runtime = ToolRuntime(mcp_catalog_path=tmp_path / "c.json")
    await runtime.start()
    assert runtime.registry.unregister("echo") is True
    assert runtime.registry.unregister("echo") is False
    removed = runtime.registry.clear_source(ToolSource.MCP)
    assert removed >= 0
    assert runtime.list_tools(source=ToolSource.MCP) == []
    await runtime.stop()


@pytest.mark.asyncio
async def test_concurrent_invokes(tmp_path: Path) -> None:
    runtime = ToolRuntime(mcp_catalog_path=tmp_path / "c.json")
    await runtime.start()

    async def one(i: int) -> bool:
        result = await runtime.invoke("math.eval", {"expression": f"{i}+{i}"})
        return result.success and result.output.get("value") == i * 2

    outcomes = await asyncio.gather(*(one(i) for i in range(1, 16)))
    assert all(outcomes)
    await runtime.stop()


@pytest.mark.asyncio
async def test_math_edges_and_text_stats(tmp_path: Path) -> None:
    runtime = ToolRuntime(mcp_catalog_path=tmp_path / "c.json")
    await runtime.start()
    div = await runtime.invoke("math.eval", {"expression": "9//2"})
    assert div.success and div.output["value"] == 4
    unary = await runtime.invoke("math.eval", {"expression": "-3+5"})
    assert unary.success and unary.output["value"] == 2
    empty = await runtime.invoke("math.eval", {"expression": ""})
    assert empty.success is False
    stats = await runtime.invoke("text.stats", {"text": ""})
    assert stats.success and stats.output["words"] == 0
    await runtime.stop()


@pytest.mark.asyncio
async def test_denied_emits_tool_denied_event(tmp_path: Path) -> None:
    bus = InProcessEventBus()
    await bus.start()
    seen: list[str] = []

    async def capture(event_type: str, _payload: dict[str, object]) -> None:
        seen.append(event_type)

    bus.subscribe("tool.*", capture)
    registry = ToolRegistry()

    async def _handler(_args):  # type: ignore[no-untyped-def]
        return {"ok": True}

    registry.register(
        ToolSpec(
            name="desk.act",
            title="Desktop",
            permissions=[ToolPermissionLevel.DESKTOP],
            source=ToolSource.BUILTIN,
        ),
        _handler,
    )
    executor = ToolExecutor(
        registry,
        PermissionPolicy(SimpleNamespace(desktop_control=False, tool_allow_execute=False)),
        event_bus=bus,
    )
    result = await executor.invoke(ToolInvocation(tool_name="desk.act"))
    await bus.stop()
    assert result.denied is True
    assert "tool.denied" in seen
