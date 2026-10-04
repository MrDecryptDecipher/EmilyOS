"""Integration: browser subsystem + tools via kernel."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from emily.browser.subsystem import BrowserSubsystem
from emily.config.settings import EmilySettings
from emily.core.types.tool import ToolPermissionLevel
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.tools.models import CapabilityToken
from emily.tools.subsystem import ToolsSubsystem

pytestmark = pytest.mark.asyncio


async def test_providers_style_kernel_browser_roundtrip(tmp_path: Path) -> None:
    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        nvidia_api_key=SecretStr(""),
        routesme_api_key=SecretStr(""),
        tools_enabled=True,
        mcp_catalog_path=tmp_path / "catalog.json",
        browser_enabled=True,
        allow_browser=True,
        browser_automation=True,
        browser_headless=True,
        browser_profiles_directory=tmp_path / "profiles",
        _env_file=None,
    )
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ToolsSubsystem(mcp_catalog_path=tmp_path / "catalog.json"))
    kernel.register(BrowserSubsystem(profiles_dir=tmp_path / "profiles"))
    ctx = await kernel.start()
    try:
        assert ctx.browser_runtime is not None
        result = await ctx.tool_runtime.invoke(  # type: ignore[union-attr]
            "browser.goto",
            {"url": "data:text/html,<html><body>m7</body></html>"},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.BROWSER]),
        )
        assert result.success is True
        evaled = await ctx.tool_runtime.invoke(  # type: ignore[union-attr]
            "browser.eval",
            {"expression": "document.body.textContent"},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.BROWSER]),
        )
        assert evaled.success is True
        assert "m7" in str(evaled.output.get("result"))
    finally:
        await kernel.stop()
