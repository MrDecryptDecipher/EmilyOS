"""Register browser actions as tools."""

from __future__ import annotations

from typing import Any

from emily.browser.runtime import BrowserRuntime
from emily.core.types.tool import ToolPermissionLevel
from emily.tools.models import ToolSource, ToolSpec
from emily.tools.registry import ToolRegistry


def register_browser_tools(registry: ToolRegistry, runtime: BrowserRuntime) -> list[str]:
    names: list[str] = []

    async def open_browser(args: dict[str, Any]) -> dict[str, Any]:
        profile = args.get("profile")
        return await runtime.open(profile=str(profile) if profile else None)

    async def goto(args: dict[str, Any]) -> dict[str, Any]:
        tab = await runtime.goto(str(args.get("url", "")))
        return tab.model_dump(mode="json")

    async def snapshot(_args: dict[str, Any]) -> dict[str, Any]:
        return (await runtime.snapshot()).model_dump(mode="json")

    async def click(args: dict[str, Any]) -> dict[str, Any]:
        return await runtime.click(
            selector=args.get("selector"),
            ref=args.get("ref"),
            role=args.get("role"),
            name=args.get("name"),
        )

    async def type_text(args: dict[str, Any]) -> dict[str, Any]:
        return await runtime.type_text(
            str(args.get("text", "")),
            selector=args.get("selector"),
            ref=args.get("ref"),
            role=args.get("role"),
            name=args.get("name"),
            clear=bool(args.get("clear", False)),
        )

    async def tabs(_args: dict[str, Any]) -> dict[str, Any]:
        return {"tabs": [t.model_dump(mode="json") for t in await runtime.tabs()]}

    async def evaluate(args: dict[str, Any]) -> dict[str, Any]:
        result = await runtime.evaluate(str(args.get("expression", "")))
        return {"result": result}

    async def close(_args: dict[str, Any]) -> dict[str, Any]:
        await runtime.close()
        return {"closed": True}

    specs: list[tuple[ToolSpec, Any]] = [
        (
            ToolSpec(
                name="browser.open",
                title="Open Browser",
                description="Open Chromium with a persistent profile",
                permissions=[ToolPermissionLevel.BROWSER],
                source=ToolSource.PLUGIN,
                input_schema={"type": "object", "properties": {"profile": {"type": "string"}}},
                metadata={"subsystem": "browser"},
            ),
            open_browser,
        ),
        (
            ToolSpec(
                name="browser.goto",
                title="Navigate",
                description="Navigate the active tab to a URL",
                permissions=[ToolPermissionLevel.BROWSER],
                source=ToolSource.PLUGIN,
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
                metadata={"subsystem": "browser"},
            ),
            goto,
        ),
        (
            ToolSpec(
                name="browser.snapshot",
                title="DOM Snapshot",
                description="Capture accessibility/DOM grounding snapshot",
                permissions=[ToolPermissionLevel.BROWSER],
                source=ToolSource.PLUGIN,
                input_schema={"type": "object", "properties": {}},
                metadata={"subsystem": "browser"},
            ),
            snapshot,
        ),
        (
            ToolSpec(
                name="browser.click",
                title="Click",
                description="Click by CSS selector, role/name, or grounding ref",
                permissions=[ToolPermissionLevel.BROWSER],
                source=ToolSource.PLUGIN,
                input_schema={
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "ref": {"type": "string"},
                        "role": {"type": "string"},
                        "name": {"type": "string"},
                    },
                },
                metadata={"subsystem": "browser"},
            ),
            click,
        ),
        (
            ToolSpec(
                name="browser.type",
                title="Type Text",
                description="Type into an element by selector/role/ref",
                permissions=[ToolPermissionLevel.BROWSER],
                source=ToolSource.PLUGIN,
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "selector": {"type": "string"},
                        "ref": {"type": "string"},
                        "role": {"type": "string"},
                        "name": {"type": "string"},
                        "clear": {"type": "boolean"},
                    },
                    "required": ["text"],
                },
                metadata={"subsystem": "browser"},
            ),
            type_text,
        ),
        (
            ToolSpec(
                name="browser.tabs",
                title="List Tabs",
                description="List open browser tabs",
                permissions=[ToolPermissionLevel.BROWSER],
                source=ToolSource.PLUGIN,
                input_schema={"type": "object", "properties": {}},
                metadata={"subsystem": "browser"},
            ),
            tabs,
        ),
        (
            ToolSpec(
                name="browser.eval",
                title="Evaluate JavaScript",
                description="Evaluate a JS expression in the page",
                permissions=[ToolPermissionLevel.BROWSER],
                source=ToolSource.PLUGIN,
                input_schema={
                    "type": "object",
                    "properties": {"expression": {"type": "string"}},
                    "required": ["expression"],
                },
                metadata={"subsystem": "browser"},
            ),
            evaluate,
        ),
        (
            ToolSpec(
                name="browser.close",
                title="Close Browser",
                description="Close the browser context",
                permissions=[ToolPermissionLevel.BROWSER],
                source=ToolSource.PLUGIN,
                input_schema={"type": "object", "properties": {}},
                metadata={"subsystem": "browser"},
            ),
            close,
        ),
    ]
    for spec, handler in specs:
        registry.register(spec, handler)
        names.append(spec.name)
    return names
