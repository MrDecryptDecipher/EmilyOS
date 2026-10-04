"""Register desktop actions as tools."""

from __future__ import annotations

from typing import Any

from emily.core.types.tool import ToolPermissionLevel
from emily.desktop.runtime import DesktopRuntime
from emily.tools.models import ToolSource, ToolSpec
from emily.tools.registry import ToolRegistry


def register_desktop_tools(registry: ToolRegistry, runtime: DesktopRuntime) -> list[str]:
    """Register desktop tools; returns registered tool names."""

    names: list[str] = []

    async def list_windows(_args: dict[str, Any]) -> dict[str, Any]:
        windows = await runtime.list_windows()
        return {"windows": [w.model_dump(mode="json") for w in windows]}

    async def focus_window(args: dict[str, Any]) -> dict[str, Any]:
        window = await runtime.focus_window(
            args.get("window_id"),
            title=args.get("title"),
        )
        return window.model_dump(mode="json")

    async def clipboard_get(_args: dict[str, Any]) -> dict[str, Any]:
        return (await runtime.clipboard_get()).model_dump(mode="json")

    async def clipboard_set(args: dict[str, Any]) -> dict[str, Any]:
        return (await runtime.clipboard_set(str(args.get("text", "")))).model_dump(mode="json")

    async def type_text(args: dict[str, Any]) -> dict[str, Any]:
        return (await runtime.type_text(str(args.get("text", "")))).model_dump(mode="json")

    async def click(args: dict[str, Any]) -> dict[str, Any]:
        return (
            await runtime.click(int(args.get("x", 0)), int(args.get("y", 0)), button=str(args.get("button", "left")))
        ).model_dump(mode="json")

    async def powershell(args: dict[str, Any]) -> dict[str, Any]:
        return (
            await runtime.powershell(
                str(args.get("command", "")),
                timeout_seconds=float(args.get("timeout_seconds", 15.0)),
                dry_run=bool(args.get("dry_run", False)),
            )
        ).model_dump(mode="json")

    async def registry_get(args: dict[str, Any]) -> dict[str, Any]:
        return (
            await runtime.registry_get(str(args.get("path", "")), str(args.get("name", "")))
        ).model_dump(mode="json")

    async def registry_set(args: dict[str, Any]) -> dict[str, Any]:
        raw = args.get("value", "")
        value: str | int | bool
        if isinstance(raw, (bool, int)):
            value = raw
        else:
            value = str(raw)
        return (
            await runtime.registry_set(str(args.get("path", "")), str(args.get("name", "")), value)
        ).model_dump(mode="json")

    specs: list[tuple[ToolSpec, Any]] = [
        (
            ToolSpec(
                name="desktop.windows.list",
                title="List Windows",
                description="List desktop windows",
                permissions=[ToolPermissionLevel.DESKTOP],
                source=ToolSource.PLUGIN,
                input_schema={"type": "object", "properties": {}},
                metadata={"subsystem": "desktop"},
            ),
            list_windows,
        ),
        (
            ToolSpec(
                name="desktop.window.focus",
                title="Focus Window",
                description="Focus a window by id or title substring",
                permissions=[ToolPermissionLevel.DESKTOP],
                source=ToolSource.PLUGIN,
                input_schema={
                    "type": "object",
                    "properties": {
                        "window_id": {"type": "string"},
                        "title": {"type": "string"},
                    },
                },
                metadata={"subsystem": "desktop"},
            ),
            focus_window,
        ),
        (
            ToolSpec(
                name="desktop.clipboard.get",
                title="Clipboard Get",
                description="Read clipboard text",
                permissions=[ToolPermissionLevel.DESKTOP],
                source=ToolSource.PLUGIN,
                input_schema={"type": "object", "properties": {}},
                metadata={"subsystem": "desktop"},
            ),
            clipboard_get,
        ),
        (
            ToolSpec(
                name="desktop.clipboard.set",
                title="Clipboard Set",
                description="Write clipboard text",
                permissions=[ToolPermissionLevel.DESKTOP],
                source=ToolSource.PLUGIN,
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                metadata={"subsystem": "desktop"},
            ),
            clipboard_set,
        ),
        (
            ToolSpec(
                name="desktop.input.type",
                title="Type Text",
                description="Type or record text input",
                permissions=[ToolPermissionLevel.DESKTOP],
                source=ToolSource.PLUGIN,
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                metadata={"subsystem": "desktop"},
            ),
            type_text,
        ),
        (
            ToolSpec(
                name="desktop.input.click",
                title="Click",
                description="Click or record a click at coordinates",
                permissions=[ToolPermissionLevel.DESKTOP],
                source=ToolSource.PLUGIN,
                input_schema={
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"},
                        "y": {"type": "integer"},
                        "button": {"type": "string"},
                    },
                    "required": ["x", "y"],
                },
                metadata={"subsystem": "desktop"},
            ),
            click,
        ),
        (
            ToolSpec(
                name="desktop.powershell",
                title="PowerShell",
                description="Run a PowerShell command (policy gated)",
                permissions=[ToolPermissionLevel.DESKTOP, ToolPermissionLevel.EXECUTE],
                source=ToolSource.PLUGIN,
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "timeout_seconds": {"type": "number"},
                        "dry_run": {"type": "boolean"},
                    },
                    "required": ["command"],
                },
                metadata={"subsystem": "desktop"},
            ),
            powershell,
        ),
        (
            ToolSpec(
                name="desktop.registry.get",
                title="Registry Get",
                description="Read an allowlisted registry value",
                permissions=[ToolPermissionLevel.DESKTOP],
                source=ToolSource.PLUGIN,
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "name": {"type": "string"},
                    },
                    "required": ["path", "name"],
                },
                metadata={"subsystem": "desktop"},
            ),
            registry_get,
        ),
        (
            ToolSpec(
                name="desktop.registry.set",
                title="Registry Set",
                description="Write an allowlisted registry value",
                permissions=[ToolPermissionLevel.DESKTOP, ToolPermissionLevel.PRIVILEGED],
                source=ToolSource.PLUGIN,
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "name": {"type": "string"},
                        "value": {},
                    },
                    "required": ["path", "name", "value"],
                },
                metadata={"subsystem": "desktop"},
            ),
            registry_set,
        ),
    ]

    for spec, handler in specs:
        registry.register(spec, handler)
        names.append(spec.name)
    return names
