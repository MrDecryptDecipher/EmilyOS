"""Desktop policy gate."""

from __future__ import annotations

from typing import Any

from emily.desktop.errors import DesktopPolicyError
from emily.desktop.models import DesktopAction


class DesktopPolicy:
    """Enforces settings-based allow/deny for desktop actions."""

    def __init__(self, settings: Any | None = None) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        if self.settings is None:
            return True
        return bool(getattr(self.settings, "desktop_control", False))

    @property
    def live(self) -> bool:
        if self.settings is None:
            return False
        return bool(getattr(self.settings, "desktop_live", False))

    def require_desktop(self) -> None:
        if not self.enabled:
            raise DesktopPolicyError("desktop_control is disabled")

    def allow_powershell(self) -> None:
        self.require_desktop()
        if self.settings is None:
            return
        if not (
            bool(getattr(self.settings, "allow_terminal", False))
            or bool(getattr(self.settings, "allow_system_commands", False))
            or bool(getattr(self.settings, "desktop_powershell_enabled", False))
        ):
            raise DesktopPolicyError("PowerShell requires allow_terminal/system_commands/desktop_powershell")

    def allow_registry_read(self) -> None:
        self.require_desktop()
        if self.settings is None:
            return
        if not bool(getattr(self.settings, "desktop_registry_enabled", True)):
            raise DesktopPolicyError("desktop registry access disabled")

    def allow_registry_write(self) -> None:
        self.allow_registry_read()
        if self.settings is None:
            return
        if not (
            bool(getattr(self.settings, "allow_system_commands", False))
            or bool(getattr(self.settings, "desktop_registry_write", False))
        ):
            raise DesktopPolicyError("registry write requires allow_system_commands or desktop_registry_write")

    def check_action(self, action: DesktopAction) -> None:
        if action in {
            DesktopAction.LIST_WINDOWS,
            DesktopAction.FOCUS_WINDOW,
            DesktopAction.CLIPBOARD_GET,
            DesktopAction.CLIPBOARD_SET,
            DesktopAction.TYPE_TEXT,
            DesktopAction.CLICK,
        }:
            self.require_desktop()
            return
        if action == DesktopAction.POWERSHELL:
            self.allow_powershell()
            return
        if action == DesktopAction.REGISTRY_GET:
            self.allow_registry_read()
            return
        if action == DesktopAction.REGISTRY_SET:
            self.allow_registry_write()
            return
        raise DesktopPolicyError(f"unknown desktop action: {action}")

    def registry_path_allowed(self, path: str) -> bool:
        prefixes = getattr(self.settings, "desktop_registry_allow_prefixes", None)
        if not prefixes:
            prefixes = [
                "HKCU\\Software\\EmilyOS",
                "HKCU\\Software\\Emily",
            ]
        normalized = path.replace("/", "\\")
        return any(normalized.lower().startswith(str(p).lower()) for p in prefixes)
