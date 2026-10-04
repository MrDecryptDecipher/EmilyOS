"""Milestone 5 in-depth smoke harness (offline-first)."""

from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pydantic import SecretStr

from emily.config.settings import EmilySettings
from emily.core.types.tool import ToolPermissionLevel
from emily.events.bus import InProcessEventBus
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.tools.executor import ToolExecutor
from emily.tools.models import (
    CapabilityToken,
    MCPCatalog,
    MCPServerDescriptor,
    MCPToolDescriptor,
    ToolInvocation,
    ToolSource,
    ToolSpec,
)
from emily.tools.policy import PermissionPolicy
from emily.tools.registry import ToolRegistry
from emily.tools.runtime import ToolRuntime
from emily.tools.subsystem import ToolsSubsystem


@dataclass
class ProbeResult:
    name: str
    ok: bool
    detail: str


async def probe_builtins(root: Path) -> ProbeResult:
    runtime = ToolRuntime(mcp_catalog_path=root / "c1.json")
    await runtime.start()
    echo = await runtime.invoke("echo", {"message": "ok"})
    math = await runtime.invoke("math.eval", {"expression": "7*8"})
    text = await runtime.invoke("text.stats", {"text": "a b c"})
    ok = (
        echo.success
        and math.success
        and math.output.get("value") == 56
        and text.success
        and text.output.get("words") == 3
    )
    await runtime.stop()
    return ProbeResult("tool:builtins", ok, f"math={math.output} words={text.output.get('words')}")


async def probe_capability_isolation(root: Path) -> ProbeResult:
    runtime = ToolRuntime(mcp_catalog_path=root / "c2.json")
    await runtime.start()
    denied = await runtime.invoke(
        "math.eval",
        {"expression": "1+1"},
        capabilities=CapabilityToken(granted=[ToolPermissionLevel.READ]),
    )
    allowed = await runtime.invoke(
        "echo",
        {"message": "x"},
        capabilities=CapabilityToken(granted=[ToolPermissionLevel.READ]),
    )
    ok = bool(denied.denied) and bool(allowed.success)
    await runtime.stop()
    return ProbeResult("tool:capability", ok, f"denied={denied.denied} allowed={allowed.success}")


async def probe_policy_deny(root: Path) -> ProbeResult:
    registry = ToolRegistry()

    async def _handler(_args: dict[str, object]) -> dict[str, object]:
        return {"ok": True}

    registry.register(
        ToolSpec(
            name="net.get",
            title="Net",
            permissions=[ToolPermissionLevel.NETWORK],
            source=ToolSource.BUILTIN,
        ),
        _handler,
    )
    executor = ToolExecutor(
        registry,
        PermissionPolicy(SimpleNamespace(allow_network=False, tool_allow_execute=False)),
    )
    result = await executor.invoke(ToolInvocation(tool_name="net.get"))
    ok = bool(result.denied) and "network" in (result.error or "")
    return ProbeResult("tool:policy_deny", ok, f"error={result.error}")


async def probe_mcp_hot_reload(root: Path) -> ProbeResult:
    catalog_path = root / "catalog.json"
    catalog_path.write_text(
        json.dumps(
            MCPCatalog(
                servers=[
                    MCPServerDescriptor(
                        name="s1",
                        tools=[
                            MCPToolDescriptor(
                                name="mcp.reload.a",
                                permissions=[ToolPermissionLevel.READ],
                            )
                        ],
                    )
                ]
            ).model_dump(mode="json")
        ),
        encoding="utf-8",
    )
    runtime = ToolRuntime(mcp_catalog_path=catalog_path)
    await runtime.start()
    catalog_path.write_text(
        json.dumps(
            MCPCatalog(
                servers=[
                    MCPServerDescriptor(
                        name="s2",
                        tools=[
                            MCPToolDescriptor(
                                name="mcp.reload.b",
                                permissions=[ToolPermissionLevel.READ],
                            )
                        ],
                    )
                ]
            ).model_dump(mode="json")
        ),
        encoding="utf-8",
    )
    stats = await runtime.reload_mcp_async()
    names = {t.name for t in runtime.list_tools()}
    ok = "mcp.reload.b" in names and "mcp.reload.a" not in names and stats["added"] == 1
    await runtime.stop()
    return ProbeResult("tool:mcp_reload", ok, f"stats={stats}")


async def probe_events(root: Path) -> ProbeResult:
    bus = InProcessEventBus()
    await bus.start()
    seen: list[str] = []

    async def capture(event_type: str, _payload: dict[str, object]) -> None:
        seen.append(event_type)

    bus.subscribe("tool.*", capture)
    bus.subscribe("mcp.*", capture)
    runtime = ToolRuntime(event_bus=bus, mcp_catalog_path=root / "c3.json")
    await runtime.start()
    await runtime.invoke("echo", {"message": "evt"})
    await runtime.invoke(
        "math.eval",
        {"expression": "1+1"},
        capabilities=CapabilityToken(granted=[ToolPermissionLevel.READ]),
    )
    await runtime.reload_mcp_async()
    await runtime.stop()
    await bus.stop()
    required = {"tool.invoked", "tool.denied", "mcp.reloaded"}
    ok = required.issubset(set(seen))
    return ProbeResult("tool:events", ok, f"seen={sorted(set(seen))}")


async def probe_concurrency(root: Path) -> ProbeResult:
    runtime = ToolRuntime(mcp_catalog_path=root / "c4.json")
    await runtime.start()

    async def one(i: int) -> bool:
        result = await runtime.invoke("echo", {"message": f"n{i}"})
        return result.success and result.output.get("message") == f"n{i}"

    outcomes = await asyncio.gather(*(one(i) for i in range(20)))
    ok = all(outcomes)
    await runtime.stop()
    return ProbeResult("tool:concurrency", ok, f"ok={sum(1 for o in outcomes if o)}/20")


async def probe_kernel_stack(root: Path) -> ProbeResult:
    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        nvidia_api_key=SecretStr(""),
        routesme_api_key=SecretStr(""),
        tools_enabled=True,
        mcp_catalog_path=root / "k-mcp" / "catalog.json",
        tool_allow_execute=True,
        allow_network=False,
        _env_file=None,
    )
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ToolsSubsystem(mcp_catalog_path=root / "k-mcp" / "catalog.json"))
    ctx = await kernel.start()
    try:
        assert ctx.tool_runtime is not None
        # Empty catalog by default — no demo/stub MCP tools.
        assert ctx.tool_runtime.list_tools(source=__import__("emily.tools.models", fromlist=["ToolSource"]).ToolSource.MCP) == []
        echo = await ctx.tool_runtime.invoke("echo", {"message": "hi"})
        health = await kernel.health()
        report = next(s for s in health["subsystems"] if s["name"] == "tools")
        ok = echo.success and report["healthy"] is True and report["details"]["tools_total"] >= 4
        return ProbeResult(
            "tool:kernel",
            ok,
            f"tools={report['details']['tools_total']} echo_ok={echo.success}",
        )
    finally:
        await kernel.stop()


async def probe_disabled_tool(root: Path) -> ProbeResult:
    runtime = ToolRuntime(mcp_catalog_path=root / "c5.json")
    await runtime.start()
    runtime.registry.get("clock.now").spec.enabled = False
    result = await runtime.invoke("clock.now", {})
    ok = bool(result.denied) and result.error == "tool disabled"
    await runtime.stop()
    return ProbeResult("tool:disabled", ok, f"error={result.error}")


async def main() -> int:
    with tempfile.TemporaryDirectory(prefix="emily-m5-smoke-") as tmp:
        root = Path(tmp)
        results = [
            await probe_builtins(root),
            await probe_capability_isolation(root),
            await probe_policy_deny(root),
            await probe_mcp_hot_reload(root),
            await probe_events(root),
            await probe_concurrency(root),
            await probe_kernel_stack(root),
            await probe_disabled_tool(root),
        ]
    payload: dict[str, Any] = {
        "results": [asdict(r) for r in results],
        "passed": sum(1 for r in results if r.ok),
        "failed": sum(1 for r in results if not r.ok),
        "total": len(results),
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
