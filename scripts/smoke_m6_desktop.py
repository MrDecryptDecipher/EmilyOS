"""Milestone 6 smoke harness — real Windows desktop only."""

from __future__ import annotations

import asyncio
import sys
import winreg
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from pydantic import SecretStr

from emily.config.settings import EmilySettings
from emily.core.types.tool import ToolPermissionLevel
from emily.desktop.errors import DesktopPolicyError
from emily.desktop.runtime import DesktopRuntime
from emily.desktop.subsystem import DesktopSubsystem
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.tools.models import CapabilityToken
from emily.tools.subsystem import ToolsSubsystem


@dataclass
class ProbeResult:
    name: str
    ok: bool
    detail: str


def _settings(**extra: object) -> SimpleNamespace:
    data = {
        "desktop_control": True,
        "desktop_live": True,
        "allow_terminal": True,
        "allow_system_commands": True,
        "desktop_powershell_enabled": True,
        "desktop_registry_enabled": True,
        "desktop_registry_write": True,
        "desktop_registry_allow_prefixes": ["HKCU\\Software\\EmilyOS"],
    }
    data.update(extra)
    return SimpleNamespace(**data)


async def probe_windows_clipboard() -> ProbeResult:
    runtime = DesktopRuntime(settings=_settings(), live=True)
    await runtime.start()
    windows = await runtime.list_windows()
    previous = await runtime.clipboard_get()
    marker = "smoke-m6-real-clipboard"
    try:
        await runtime.clipboard_set(marker)
        clip = await runtime.clipboard_get()
        ok = isinstance(windows, list) and clip.text == marker
        detail = f"windows={len(windows)} clip_ok={clip.text == marker}"
    finally:
        await runtime.clipboard_set(previous.text)
        await runtime.stop()
    return ProbeResult("desktop:windows+clipboard", ok, detail)


async def probe_powershell_registry() -> ProbeResult:
    runtime = DesktopRuntime(settings=_settings(), live=True)
    path = "HKCU\\Software\\EmilyOS\\Config"
    name = "SmokeM6"
    try:
        ps = await runtime.powershell("Write-Output 'smoke-m6-ps'")
        await runtime.registry_set(path, name, "ok")
        value = await runtime.registry_get(path, name)
        denied = False
        try:
            await runtime.registry_get("HKLM\\Software\\Evil", "X")
        except DesktopPolicyError:
            denied = True
        ok = ps.exit_code == 0 and "smoke-m6-ps" in ps.stdout and value.value == "ok" and denied
        return ProbeResult("desktop:powershell+registry", ok, f"ps_exit={ps.exit_code} denied={denied}")
    finally:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Software\EmilyOS\Config", 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, name)
        except OSError:
            pass


async def probe_policy_deny() -> ProbeResult:
    runtime = DesktopRuntime(
        settings=SimpleNamespace(desktop_control=False, desktop_live=True),
        live=True,
    )
    denied = False
    try:
        await runtime.list_windows()
    except DesktopPolicyError:
        denied = True
    return ProbeResult("desktop:policy", denied, f"denied={denied}")


async def probe_kernel_tools(root: Path) -> ProbeResult:
    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        nvidia_api_key=SecretStr(""),
        routesme_api_key=SecretStr(""),
        tools_enabled=True,
        mcp_catalog_path=root / "catalog.json",
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
    kernel.register(ToolsSubsystem(mcp_catalog_path=root / "catalog.json"))
    kernel.register(DesktopSubsystem())
    ctx = await kernel.start()
    try:
        assert ctx.tool_runtime is not None
        result = await ctx.tool_runtime.invoke(
            "desktop.windows.list",
            {},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.DESKTOP]),
        )
        health = await kernel.health()
        desktop = next(s for s in health["subsystems"] if s["name"] == "desktop")
        ok = result.success and desktop["healthy"] and desktop["details"].get("backend") == "windows"
        return ProbeResult(
            "desktop:kernel+tools",
            ok,
            f"tools_ok={result.success} backend={desktop['details'].get('backend')}",
        )
    finally:
        await kernel.stop()


async def main() -> int:
    if sys.platform != "win32":
        print("FAIL: desktop smoke requires Windows")
        return 1

    import tempfile

    root = Path(tempfile.mkdtemp(prefix="emily-m6-"))
    probes = [
        await probe_windows_clipboard(),
        await probe_powershell_registry(),
        await probe_policy_deny(),
        await probe_kernel_tools(root),
    ]
    width = max(len(p.name) for p in probes)
    passed = 0
    for probe in probes:
        mark = "PASS" if probe.ok else "FAIL"
        print(f"[{mark}] {probe.name:<{width}}  {probe.detail}")
        if probe.ok:
            passed += 1
    print(f"\n{passed}/{len(probes)} probes passed (real Windows)")
    return 0 if passed == len(probes) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
