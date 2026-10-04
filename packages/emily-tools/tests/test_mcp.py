"""MCP discovery and live stdio registration tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from emily.core.types.tool import ToolPermissionLevel
from emily.tools.models import MCPCatalog, MCPServerDescriptor, MCPToolDescriptor, ToolSource
from emily.tools.runtime import ToolRuntime


@pytest.mark.asyncio
async def test_empty_catalog_by_default(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.json"
    runtime = ToolRuntime(mcp_catalog_path=catalog)
    await runtime.start()
    assert catalog.exists()
    assert runtime.list_tools(source=ToolSource.MCP) == []
    await runtime.stop()


@pytest.mark.asyncio
async def test_live_stdio_mcp_invoke(tmp_path: Path) -> None:
    server_script = Path(__file__).with_name("mcp_test_server.py")
    catalog_path = tmp_path / "catalog.json"
    catalog = MCPCatalog(
        servers=[
            MCPServerDescriptor(
                name="test",
                transport="stdio",
                command=sys.executable,
                args=[str(server_script)],
                enabled=True,
                tools=[
                    MCPToolDescriptor(
                        name="ping",
                        description="Ping",
                        permissions=[ToolPermissionLevel.READ, ToolPermissionLevel.EXECUTE],
                    )
                ],
            )
        ]
    )
    catalog_path.write_text(json.dumps(catalog.model_dump(mode="json")), encoding="utf-8")
    runtime = ToolRuntime(
        mcp_catalog_path=catalog_path,
        settings=type("S", (), {"tool_allow_execute": True, "desktop_control": False})(),
    )
    await runtime.start()
    try:
        names = {t.name for t in runtime.list_tools(source=ToolSource.MCP)}
        assert any(name.endswith("ping") for name in names)
        tool_name = next(iter(names))
        result = await runtime.invoke(tool_name, {"ping": "hi"})
        assert result.success is True
        assert result.output["mode"] == "mcp-live"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_hot_reload_swaps_live_servers(tmp_path: Path) -> None:
    server_script = Path(__file__).with_name("mcp_test_server.py")
    catalog_path = tmp_path / "catalog.json"
    catalog = MCPCatalog(
        servers=[
            MCPServerDescriptor(
                name="alpha",
                transport="stdio",
                command=sys.executable,
                args=[str(server_script)],
                enabled=True,
            )
        ]
    )
    catalog_path.write_text(json.dumps(catalog.model_dump(mode="json")), encoding="utf-8")
    runtime = ToolRuntime(
        mcp_catalog_path=catalog_path,
        settings=type("S", (), {"tool_allow_execute": True})(),
    )
    await runtime.start()
    try:
        assert runtime.list_tools(source=ToolSource.MCP)
        catalog2 = MCPCatalog(servers=[])
        catalog_path.write_text(json.dumps(catalog2.model_dump(mode="json")), encoding="utf-8")
        stats = await runtime.reload_mcp_async()
        assert stats["added"] == 0
        assert runtime.list_tools(source=ToolSource.MCP) == []
    finally:
        await runtime.stop()
