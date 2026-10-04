"""Kernel integration for tools subsystem."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from emily.config.settings import EmilySettings
from emily.core.types.tool import ToolPermissionLevel
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.tools.models import CapabilityToken
from emily.tools.subsystem import ToolsSubsystem


@pytest.mark.asyncio
async def test_tools_subsystem_lists_and_invokes(tmp_path: Path) -> None:
    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        nvidia_api_key=SecretStr(""),
        routesme_api_key=SecretStr(""),
        tools_enabled=True,
        mcp_catalog_path=tmp_path / "catalog.json",
        _env_file=None,
    )
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ToolsSubsystem(mcp_catalog_path=tmp_path / "catalog.json"))
    ctx = await kernel.start()
    try:
        assert ctx.tool_runtime is not None
        tools = ctx.tool_runtime.list_tools()
        assert any(t.name == "echo" for t in tools)
        result = await ctx.tool_runtime.invoke(
            "echo",
            {"message": "kernel"},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.READ]),
        )
        assert result.success is True
        health = await kernel.health()
        report = next(s for s in health["subsystems"] if s["name"] == "tools")
        assert report["healthy"] is True
        assert report["details"]["tools_total"] >= 4
    finally:
        await kernel.stop()
        assert ctx.tool_runtime is None
