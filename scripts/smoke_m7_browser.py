"""Milestone 7 smoke — real Playwright browser."""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from pydantic import SecretStr

from emily.browser.errors import BrowserPolicyError
from emily.browser.runtime import BrowserRuntime
from emily.browser.subsystem import BrowserSubsystem
from emily.config.settings import EmilySettings
from emily.core.types.tool import ToolPermissionLevel
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.tools.models import CapabilityToken
from emily.tools.subsystem import ToolsSubsystem


@dataclass
class ProbeResult:
    name: str
    ok: bool
    detail: str


def _settings(root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        allow_browser=True,
        browser_automation=True,
        browser_headless=True,
        browser_default_profile="smoke",
        browser_profiles_directory=root / "profiles",
        browser_url_allow_prefixes=[],
        browser_channel=None,
    )


async def probe_navigation(root: Path) -> ProbeResult:
    runtime = BrowserRuntime(settings=_settings(root))
    await runtime.start()
    try:
        await runtime.open()
        await runtime.goto(
            "data:text/html,<html><body><h1 id='t'>smoke</h1><a href='#'>Link</a></body></html>"
        )
        grounding = await runtime.snapshot()
        text = await runtime.evaluate("document.getElementById('t').textContent")
        ok = text == "smoke" and grounding.nodes
        return ProbeResult("browser:nav+ground", ok, f"text={text!r} nodes={len(grounding.nodes)}")
    finally:
        await runtime.close()
        await runtime.stop()


async def probe_policy(root: Path) -> ProbeResult:
    runtime = BrowserRuntime(
        settings=SimpleNamespace(
            allow_browser=False,
            browser_automation=False,
            browser_headless=True,
            browser_default_profile="x",
            browser_profiles_directory=root / "p",
            browser_url_allow_prefixes=[],
            browser_channel=None,
        )
    )
    denied = False
    try:
        await runtime.open()
    except BrowserPolicyError:
        denied = True
    return ProbeResult("browser:policy", denied, f"denied={denied}")


async def probe_kernel(root: Path) -> ProbeResult:
    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        nvidia_api_key=SecretStr(""),
        routesme_api_key=SecretStr(""),
        tools_enabled=True,
        mcp_catalog_path=root / "catalog.json",
        browser_enabled=True,
        allow_browser=True,
        browser_automation=True,
        browser_headless=True,
        browser_profiles_directory=root / "profiles",
        _env_file=None,
    )
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ToolsSubsystem(mcp_catalog_path=root / "catalog.json"))
    kernel.register(BrowserSubsystem(profiles_dir=root / "profiles"))
    ctx = await kernel.start()
    try:
        assert ctx.tool_runtime is not None
        result = await ctx.tool_runtime.invoke(
            "browser.goto",
            {"url": "data:text/html,<html><body>kernel</body></html>"},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.BROWSER]),
        )
        health = await kernel.health()
        browser = next(s for s in health["subsystems"] if s["name"] == "browser")
        ok = result.success and browser["healthy"]
        return ProbeResult(
            "browser:kernel+tools",
            ok,
            f"ok={result.success} backend={browser['details'].get('backend')}",
        )
    finally:
        await kernel.stop()


async def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="emily-m7-"))
    probes = [
        await probe_navigation(root),
        await probe_policy(root),
        await probe_kernel(root),
    ]
    width = max(len(p.name) for p in probes)
    passed = 0
    for probe in probes:
        mark = "PASS" if probe.ok else "FAIL"
        print(f"[{mark}] {probe.name:<{width}}  {probe.detail}")
        if probe.ok:
            passed += 1
    print(f"\n{passed}/{len(probes)} probes passed (real Playwright)")
    return 0 if passed == len(probes) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
