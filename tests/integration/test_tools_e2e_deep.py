"""Deep e2e integration for Milestone 5 tools + MCP."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import SecretStr

from emily.agents.subsystem import AgentsSubsystem
from emily.config.settings import EmilySettings
from emily.core.types.memory import MemoryKind
from emily.core.types.mission import MissionStatus
from emily.core.types.tool import ToolPermissionLevel
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.memory.subsystem import MemorySubsystem
from emily.missions.models import MissionSpec
from emily.missions.subsystem import MissionsSubsystem
from emily.providers.subsystem import ProvidersSubsystem
from emily.tools.models import CapabilityToken
from emily.tools.subsystem import ToolsSubsystem


def _settings(tmp_path: Path, **kwargs: object) -> EmilySettings:
    base: dict[str, object] = {
        "environment": "test",
        "log_level": "ERROR",
        "nvidia_api_key": SecretStr(""),
        "routesme_api_key": SecretStr(""),
        "mission_llm_planner": False,
        "memory_enabled": True,
        "memory_directory": tmp_path / "memory",
        "world_directory": tmp_path / "world",
        "agent_history_directory": tmp_path / "agents",
        "tools_enabled": True,
        "mcp_catalog_path": tmp_path / "mcp" / "catalog.json",
        "tool_allow_execute": True,
        "allow_network": False,
        "desktop_control": False,
        "browser_automation": False,
        "allow_browser": False,
        "allow_file_write": False,
        "allow_terminal": False,
        "allow_system_commands": False,
        "_env_file": None,
    }
    base.update(kwargs)
    return EmilySettings(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_full_stack_tools_with_mission_memory(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ProvidersSubsystem())
    kernel.register(MemorySubsystem())
    kernel.register(ToolsSubsystem(mcp_catalog_path=tmp_path / "mcp" / "catalog.json"))
    kernel.register(MissionsSubsystem(missions_dir=tmp_path / "missions"))
    kernel.register(AgentsSubsystem(history_dir=tmp_path / "agents"))
    ctx = await kernel.start()
    try:
        assert ctx.tool_runtime is not None
        assert ctx.memory_runtime is not None

        echo = await ctx.tool_runtime.invoke("echo", {"message": "stack-ok"})
        assert echo.success is True
        assert [
            t.name for t in ctx.tool_runtime.list_tools() if t.name.startswith("mcp.")
        ] == []

        # Network tool should be denyable via policy if registered later — math works.
        math = await ctx.tool_runtime.invoke(
            "math.eval",
            {"expression": "11*3"},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.EXECUTE]),
        )
        assert math.success and math.output["value"] == 33

        from emily.missions.models import TaskStatus as _TS

        class _Exec:
            async def execute_task(self, *, mission_id: str, task: dict) -> dict:
                out = dict(task)
                out["status"] = _TS.SUCCEEDED.value
                out["result"] = f"executed:{out.get('title')}"
                return out

        assert ctx.mission_runtime is not None
        ctx.mission_runtime.set_task_executor(_Exec())
        created = await ctx.mission_runtime.create(
            MissionSpec(goal="Research tools. Draft summary.")
        )
        finished = await ctx.mission_runtime.start(created.mission_id)
        assert finished.status == MissionStatus.SUCCEEDED

        await ctx.memory_runtime.remember(
            "Tool runtime verified in full stack",
            kind=MemoryKind.EPISODIC,
            title="M5 e2e",
            importance=0.8,
        )
        stats = ctx.tool_runtime.stats()
        assert stats["tools_total"] >= 4
        assert "execute" in stats["allowed_permissions"]
        assert "network" not in stats["allowed_permissions"]

        health = await kernel.health()
        tools_report = next(s for s in health["subsystems"] if s["name"] == "tools")
        assert tools_report["healthy"] is True
        assert tools_report["details"]["tools_total"] >= 4
    finally:
        await kernel.stop()


@pytest.mark.asyncio
async def test_tools_disabled_health(tmp_path: Path) -> None:
    settings = _settings(tmp_path, tools_enabled=False)
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ToolsSubsystem())
    ctx = await kernel.start()
    try:
        assert ctx.tool_runtime is None
        health = await kernel.health()
        report = next(s for s in health["subsystems"] if s["name"] == "tools")
        assert report["healthy"] is True
        assert report["message"] == "disabled"
    finally:
        await kernel.stop()


@pytest.mark.asyncio
async def test_concurrent_tool_invokes_under_kernel(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ToolsSubsystem(mcp_catalog_path=tmp_path / "mcp" / "catalog.json"))
    ctx = await kernel.start()
    try:
        assert ctx.tool_runtime is not None

        async def one(i: int) -> bool:
            result = await ctx.tool_runtime.invoke(  # type: ignore[union-attr]
                "text.stats", {"text": f"word{i} extra"}
            )
            return result.success and result.output.get("words") == 2

        assert all(await asyncio.gather(*(one(i) for i in range(12))))
    finally:
        await kernel.stop()
