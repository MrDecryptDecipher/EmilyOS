"""Real Playwright browser runtime tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from emily.browser.errors import BrowserPolicyError
from emily.browser.grounding import nodes_from_ax_tree, resolve_selector
from emily.browser.models import DomGrounding, DomNode
from emily.browser.runtime import BrowserRuntime
from emily.browser.subsystem import BrowserSubsystem
from emily.config.settings import EmilySettings
from emily.core.types.tool import ToolPermissionLevel
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.tools.models import CapabilityToken
from emily.tools.subsystem import ToolsSubsystem


def _settings(tmp_path: Path, **extra: object) -> SimpleNamespace:
    data = {
        "allow_browser": True,
        "browser_automation": True,
        "browser_headless": True,
        "browser_default_profile": "test",
        "browser_profiles_directory": tmp_path / "profiles",
        "browser_url_allow_prefixes": [],
        "browser_channel": None,
        "browser_register_tools": True,
    }
    data.update(extra)
    return SimpleNamespace(**data)


@pytest.mark.asyncio
async def test_policy_denies_without_flags(tmp_path: Path) -> None:
    runtime = BrowserRuntime(settings=_settings(tmp_path, allow_browser=False, browser_automation=False))
    with pytest.raises(BrowserPolicyError):
        await runtime.open()


@pytest.mark.asyncio
async def test_url_allowlist(tmp_path: Path) -> None:
    runtime = BrowserRuntime(
        settings=_settings(tmp_path, browser_url_allow_prefixes=["https://example.com"])
    )
    with pytest.raises(BrowserPolicyError):
        await runtime.goto("https://evil.example/path")


def test_resolve_selector_and_ax_nodes() -> None:
    grounding = DomGrounding(
        nodes=[DomNode(ref="e1", role="button", name="Go", actionable=True, selector_hint="role=button")]
    )
    mode, payload = resolve_selector(selector="#x")
    assert mode == "css" and payload["selector"] == "#x"
    mode, payload = resolve_selector(role="link", name="More")
    assert mode == "role" and payload["name"] == "More"
    mode, payload = resolve_selector(ref="e1", grounding=grounding)
    assert mode == "role" and payload["role"] == "button"
    with pytest.raises(ValueError):
        resolve_selector()
    nodes = nodes_from_ax_tree(
        [
            {"ignored": True, "role": {"value": "button"}, "name": {"value": "x"}},
            {"role": {"value": "button"}, "name": {"value": "Go"}},
            {"role": {"value": "generic"}, "name": {"value": ""}},
            {"role": {"value": "link"}, "name": {"value": "Docs"}, "value": {"value": ""}},
        ]
    )
    assert any(n.role == "button" and n.name == "Go" for n in nodes)
    assert any(n.role == "link" for n in nodes)


@pytest.mark.asyncio
async def test_goto_snapshot_eval_and_persist(tmp_path: Path) -> None:
    runtime = BrowserRuntime(settings=_settings(tmp_path))
    await runtime.start()
    try:
        await runtime.open()
        tab = await runtime.goto("data:text/html,<html><body><h1>Emily</h1><button>Go</button></body></html>")
        assert "Emily" in tab.title or tab.url.startswith("data:")
        grounding = await runtime.snapshot()
        assert grounding.url.startswith("data:")
        assert grounding.nodes
        value = await runtime.evaluate("document.querySelector('h1').textContent")
        assert value == "Emily"
        await runtime.click(role="button", name="Go")
        tabs = await runtime.tabs()
        assert tabs
        status = await runtime.status()
        assert status.profile == "test"
        assert status.metadata.get("open") is True
        cdp = await runtime.cdp("Runtime.evaluate", {"expression": "1+1", "returnByValue": True})
        assert cdp.get("result", {}).get("value") == 2
        assert (tmp_path / "profiles" / "test").exists()
    finally:
        await runtime.close()
        await runtime.stop()


@pytest.mark.asyncio
async def test_browser_subsystem_registers_tools(tmp_path: Path) -> None:
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
        browser_default_profile="kernel",
        _env_file=None,
    )
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ToolsSubsystem(mcp_catalog_path=tmp_path / "catalog.json"))
    kernel.register(BrowserSubsystem(profiles_dir=tmp_path / "profiles"))
    ctx = await kernel.start()
    try:
        assert ctx.browser_runtime is not None
        assert ctx.tool_runtime is not None
        names = {t.name for t in ctx.tool_runtime.list_tools()}
        assert "browser.goto" in names
        opened = await ctx.tool_runtime.invoke(
            "browser.open",
            {},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.BROWSER]),
        )
        assert opened.success is True
        navigated = await ctx.tool_runtime.invoke(
            "browser.goto",
            {"url": "data:text/html,<html><body><p id='x'>ok</p><input id='i'/></body></html>"},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.BROWSER]),
        )
        assert navigated.success is True
        evaluated = await ctx.tool_runtime.invoke(
            "browser.eval",
            {"expression": "document.getElementById('x').textContent"},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.BROWSER]),
        )
        assert evaluated.success is True
        assert evaluated.output.get("result") == "ok"
        typed = await ctx.tool_runtime.invoke(
            "browser.type",
            {"text": "hi", "selector": "#i", "clear": True},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.BROWSER]),
        )
        assert typed.success is True
        snapped = await ctx.tool_runtime.invoke(
            "browser.snapshot",
            {},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.BROWSER]),
        )
        assert snapped.success is True
        listed = await ctx.tool_runtime.invoke(
            "browser.tabs",
            {},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.BROWSER]),
        )
        assert listed.success is True
        closed = await ctx.tool_runtime.invoke(
            "browser.close",
            {},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.BROWSER]),
        )
        assert closed.success is True
        health = await kernel.health()
        report = next(s for s in health["subsystems"] if s["name"] == "browser")
        assert report["healthy"] is True
        assert report["details"]["backend"] == "playwright"
    finally:
        await kernel.stop()
        assert ctx.browser_runtime is None
