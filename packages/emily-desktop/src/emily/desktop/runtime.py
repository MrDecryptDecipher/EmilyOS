"""Desktop runtime facade."""

from __future__ import annotations

from typing import Any

from emily.desktop.errors import DesktopPolicyError
from emily.desktop.models import (
    ClipboardContent,
    DesktopAction,
    DesktopSnapshot,
    DesktopWindow,
    InputEvent,
    PowerShellResult,
    RegistryValue,
)
from emily.desktop.policy import DesktopPolicy
from emily.desktop.windows import create_backend


class DesktopRuntime:
    """Primary API for desktop control actions."""

    def __init__(
        self,
        *,
        settings: Any | None = None,
        event_bus: Any | None = None,
        logger: Any | None = None,
        live: bool | None = None,
    ) -> None:
        self.settings = settings
        self.event_bus = event_bus
        self.logger = logger
        self.policy = DesktopPolicy(settings)
        use_live = True if live is None else live
        if live is None:
            use_live = bool(getattr(settings, "desktop_live", True)) if settings is not None else True
        self.backend = create_backend(live=use_live)
        self._started = False
        self._actions = 0

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    async def snapshot(self) -> DesktopSnapshot:
        windows = await self.backend.list_windows()
        clipboard = await self.backend.clipboard_get()
        return DesktopSnapshot(
            backend=self.backend.name,
            live=self.backend.name == "windows",
            windows=windows,
            clipboard=clipboard,
            input_events=len(self.backend.input_log()),
            metadata={"actions": self._actions},
        )

    async def list_windows(self) -> list[DesktopWindow]:
        self.policy.check_action(DesktopAction.LIST_WINDOWS)
        windows = await self.backend.list_windows()
        await self._emit(DesktopAction.LIST_WINDOWS, {"count": len(windows)})
        return windows

    async def focus_window(
        self, window_id: str | None = None, *, title: str | None = None
    ) -> DesktopWindow:
        self.policy.check_action(DesktopAction.FOCUS_WINDOW)
        window = await self.backend.focus_window(window_id, title=title)
        await self._emit(
            DesktopAction.FOCUS_WINDOW,
            {"window_id": window.window_id, "title": window.title},
        )
        return window

    async def clipboard_get(self) -> ClipboardContent:
        self.policy.check_action(DesktopAction.CLIPBOARD_GET)
        content = await self.backend.clipboard_get()
        await self._emit(DesktopAction.CLIPBOARD_GET, {"chars": len(content.text)})
        return content

    async def clipboard_set(self, text: str) -> ClipboardContent:
        self.policy.check_action(DesktopAction.CLIPBOARD_SET)
        content = await self.backend.clipboard_set(text)
        await self._emit(DesktopAction.CLIPBOARD_SET, {"chars": len(content.text)})
        return content

    async def type_text(self, text: str) -> InputEvent:
        self.policy.check_action(DesktopAction.TYPE_TEXT)
        event = await self.backend.type_text(text)
        await self._emit(DesktopAction.TYPE_TEXT, {"chars": len(text), "event_id": event.event_id})
        return event

    async def click(self, x: int, y: int, *, button: str = "left") -> InputEvent:
        self.policy.check_action(DesktopAction.CLICK)
        event = await self.backend.click(x, y, button=button)
        await self._emit(
            DesktopAction.CLICK,
            {"x": x, "y": y, "button": button, "event_id": event.event_id},
        )
        return event

    async def powershell(
        self,
        command: str,
        *,
        timeout_seconds: float = 15.0,
        dry_run: bool = False,
    ) -> PowerShellResult:
        self.policy.check_action(DesktopAction.POWERSHELL)
        result = await self.backend.powershell(
            command,
            timeout_seconds=timeout_seconds,
            dry_run=dry_run,
        )
        await self._emit(
            DesktopAction.POWERSHELL,
            {
                "exit_code": result.exit_code,
                "dry_run": result.dry_run,
                "duration_ms": result.duration_ms,
            },
        )
        return result

    async def registry_get(self, path: str, name: str) -> RegistryValue:
        self.policy.check_action(DesktopAction.REGISTRY_GET)
        self._require_registry_path(path)
        value = await self.backend.registry_get(path, name)
        await self._emit(
            DesktopAction.REGISTRY_GET,
            {"path": value.path, "name": value.name},
        )
        return value

    async def registry_set(self, path: str, name: str, value: str | int | bool) -> RegistryValue:
        self.policy.check_action(DesktopAction.REGISTRY_SET)
        self._require_registry_path(path)
        stored = await self.backend.registry_set(path, name, value)
        await self._emit(
            DesktopAction.REGISTRY_SET,
            {"path": stored.path, "name": stored.name},
        )
        return stored

    def stats(self) -> dict[str, Any]:
        return {
            "backend": self.backend.name,
            "live": self.backend.name == "windows",
            "desktop_control": self.policy.enabled,
            "actions": self._actions,
            "input_events": len(self.backend.input_log()),
        }

    def _require_registry_path(self, path: str) -> None:
        if not self.policy.registry_path_allowed(path):
            raise DesktopPolicyError(f"registry path not allowlisted: {path}")

    async def _emit(self, action: DesktopAction, payload: dict[str, Any]) -> None:
        self._actions += 1
        if self.logger is not None:
            self.logger.info("desktop action", action=action.value, **payload)
        if self.event_bus is None:
            return
        await self.event_bus.publish(
            f"desktop.{action.value}",
            {"action": action.value, **payload},
            source="desktop",
        )
