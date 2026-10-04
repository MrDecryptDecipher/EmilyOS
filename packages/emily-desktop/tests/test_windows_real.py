"""Unit tests for desktop policy and real Windows backend."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from emily.desktop.errors import DesktopPolicyError
from emily.desktop.models import DesktopAction
from emily.desktop.policy import DesktopPolicy
from emily.desktop.runtime import DesktopRuntime

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="desktop requires Windows")


def test_policy_requires_desktop_control() -> None:
    policy = DesktopPolicy(SimpleNamespace(desktop_control=False))
    with pytest.raises(DesktopPolicyError):
        policy.check_action(DesktopAction.LIST_WINDOWS)


def test_policy_powershell_requires_extra_flags() -> None:
    policy = DesktopPolicy(
        SimpleNamespace(
            desktop_control=True,
            allow_terminal=False,
            allow_system_commands=False,
            desktop_powershell_enabled=False,
        )
    )
    with pytest.raises(DesktopPolicyError):
        policy.check_action(DesktopAction.POWERSHELL)


def test_registry_path_allowlist() -> None:
    policy = DesktopPolicy(SimpleNamespace(desktop_registry_allow_prefixes=["HKCU\\Software\\EmilyOS"]))
    assert policy.registry_path_allowed("HKCU\\Software\\EmilyOS\\Config")
    assert not policy.registry_path_allowed("HKLM\\Software\\Evil")


def _enabled_settings(**extra: object) -> SimpleNamespace:
    base = {
        "desktop_control": True,
        "desktop_live": True,
        "allow_terminal": True,
        "allow_system_commands": True,
        "desktop_powershell_enabled": True,
        "desktop_registry_enabled": True,
        "desktop_registry_write": True,
        "desktop_registry_allow_prefixes": ["HKCU\\Software\\EmilyOS"],
    }
    base.update(extra)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_real_windows_list_and_clipboard() -> None:
    runtime = DesktopRuntime(settings=_enabled_settings(), live=True)
    await runtime.start()
    windows = await runtime.list_windows()
    assert isinstance(windows, list)
    assert all(w.window_id.startswith("hwnd:") for w in windows)

    previous = await runtime.clipboard_get()
    marker = "emily-m6-clipboard-probe"
    try:
        await runtime.clipboard_set(marker)
        assert (await runtime.clipboard_get()).text == marker
    finally:
        await runtime.clipboard_set(previous.text)
    await runtime.stop()


@pytest.mark.asyncio
async def test_real_powershell_and_registry() -> None:
    import winreg

    runtime = DesktopRuntime(settings=_enabled_settings(), live=True)
    path = "HKCU\\Software\\EmilyOS\\Config"
    name = "M6Probe"
    try:
        ps = await runtime.powershell("Write-Output 'emily-m6-ps'")
        assert ps.exit_code == 0
        assert "emily-m6-ps" in ps.stdout

        await runtime.registry_set(path, name, "ok")
        value = await runtime.registry_get(path, name)
        assert value.value == "ok"

        with pytest.raises(DesktopPolicyError):
            await runtime.registry_get("HKLM\\Software\\Evil", "X")
    finally:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\EmilyOS\Config", 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
        except OSError:
            pass


@pytest.mark.asyncio
async def test_runtime_denies_without_control() -> None:
    runtime = DesktopRuntime(
        settings=SimpleNamespace(desktop_control=False, desktop_live=True),
        live=True,
    )
    with pytest.raises(DesktopPolicyError):
        await runtime.list_windows()


@pytest.mark.asyncio
async def test_refuses_simulated_mode() -> None:
    from emily.desktop.errors import DesktopError

    with pytest.raises(DesktopError, match="simulated"):
        DesktopRuntime(settings=_enabled_settings(desktop_live=False), live=False)
