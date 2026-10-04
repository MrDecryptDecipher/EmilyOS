"""Desktop domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from emily.core.ids import new_id


class DesktopAction(StrEnum):
    LIST_WINDOWS = "list_windows"
    FOCUS_WINDOW = "focus_window"
    CLIPBOARD_GET = "clipboard_get"
    CLIPBOARD_SET = "clipboard_set"
    TYPE_TEXT = "type_text"
    CLICK = "click"
    POWERSHELL = "powershell"
    REGISTRY_GET = "registry_get"
    REGISTRY_SET = "registry_set"


class DesktopWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_id: str
    title: str
    process_name: str = ""
    pid: int = 0
    focused: bool = False
    bounds: dict[str, int] = Field(default_factory=dict)


class ClipboardContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = ""
    format: str = "text"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PowerShellResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: str
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    dry_run: bool = False
    duration_ms: float = 0.0


class RegistryValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    name: str
    value: str | int | bool | None = None
    value_type: str = "string"


class InputEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: new_id("inp"))
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DesktopSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: str
    live: bool
    windows: list[DesktopWindow] = Field(default_factory=list)
    clipboard: ClipboardContent = Field(default_factory=ClipboardContent)
    input_events: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
