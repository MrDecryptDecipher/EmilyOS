"""Kernel integration for real Windows desktop subsystem."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import SecretStr

from emily.config.settings import EmilySettings
from emily.core.types.tool import ToolPermissionLevel
from emily.desktop.subsystem import DesktopSubsystem
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.tools.models import CapabilityToken
from emily.tools.subsystem import ToolsSubsystem

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="desktop requires Windows")


@pytest.mark.asyncio
async def test_desktop_subsystem_registers_tools(tmp_path: Path) -> None:
    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        nvidia_api_key=SecretStr(""),
        routesme_api_key=SecretStr(""),
        tools_enabled=True,
        mcp_catalog_path=tmp_path / "catalog.json",
        desktop_enabled=True,
        desktop_control=True,
        desktop_live=True,
        desktop_powershell_enabled=True,
        desktop_registry_write=True,
        allow_system_commands=True,
        _env_file=None,
    )
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ToolsSubsystem(mcp_catalog_path=tmp_path / "catalog.json"))
    kernel.register(DesktopSubsystem())
    ctx = await kernel.start()
    try:
        assert ctx.desktop_runtime is not None
        assert ctx.tool_runtime is not None
        names = {t.name for t in ctx.tool_runtime.list_tools()}
        assert "desktop.windows.list" in names

        listed = await ctx.tool_runtime.invoke(
            "desktop.windows.list",
            {},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.DESKTOP]),
        )
        assert listed.success is True
        assert isinstance(listed.output.get("windows"), list)

        marker = "emily-kernel-desktop-clip"
        previous = await ctx.desktop_runtime.clipboard_get()
        try:
            clip = await ctx.tool_runtime.invoke(
                "desktop.clipboard.set",
                {"text": marker},
                capabilities=CapabilityToken(granted=[ToolPermissionLevel.DESKTOP]),
            )
            assert clip.success is True
            got = await ctx.desktop_runtime.clipboard_get()
            assert got.text == marker
        finally:
            await ctx.desktop_runtime.clipboard_set(previous.text)

        health = await kernel.health()
        report = next(s for s in health["subsystems"] if s["name"] == "desktop")
        assert report["healthy"] is True
        assert report["details"]["backend"] == "windows"
    finally:
        await kernel.stop()
        assert ctx.desktop_runtime is None
