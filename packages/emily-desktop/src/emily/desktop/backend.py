"""Desktop backend protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from emily.desktop.models import (
    ClipboardContent,
    DesktopWindow,
    InputEvent,
    PowerShellResult,
    RegistryValue,
)


@runtime_checkable
class DesktopBackend(Protocol):
    name: str

    async def list_windows(self) -> list[DesktopWindow]: ...

    async def focus_window(self, window_id: str | None = None, *, title: str | None = None) -> DesktopWindow: ...

    async def clipboard_get(self) -> ClipboardContent: ...

    async def clipboard_set(self, text: str) -> ClipboardContent: ...

    async def type_text(self, text: str) -> InputEvent: ...

    async def click(self, x: int, y: int, *, button: str = "left") -> InputEvent: ...

    async def powershell(
        self,
        command: str,
        *,
        timeout_seconds: float = 15.0,
        dry_run: bool = False,
    ) -> PowerShellResult: ...

    async def registry_get(self, path: str, name: str) -> RegistryValue: ...

    async def registry_set(self, path: str, name: str, value: str | int | bool) -> RegistryValue: ...

    def input_log(self) -> list[InputEvent]: ...
