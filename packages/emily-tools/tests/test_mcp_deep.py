"""Deep MCP catalog edge cases."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from emily.core.types.tool import ToolPermissionLevel
from emily.tools.mcp import MCPDiscovery, MCPRegistrar
from emily.tools.models import MCPCatalog, MCPServerDescriptor, MCPToolDescriptor, ToolSource
from emily.tools.registry import ToolRegistry
from emily.tools.runtime import ToolRuntime


@pytest.mark.asyncio
async def test_disabled_server_skipped_on_reload(tmp_path: Path) -> None:
    server_script = Path(__file__).with_name("mcp_test_server.py")
    catalog_path = tmp_path / "catalog.json"
    catalog = MCPCatalog(
        servers=[
            MCPServerDescriptor(
                name="off",
                enabled=False,
                transport="stdio",
                command=sys.executable,
                args=[str(server_script)],
                tools=[
                    MCPToolDescriptor(
                        name="mcp.off.tool",
                        permissions=[ToolPermissionLevel.READ],
                    )
                ],
            ),
            MCPServerDescriptor(
                name="on",
                enabled=True,
                transport="stdio",
                command=sys.executable,
                args=[str(server_script)],
                tools=[
                    MCPToolDescriptor(
                        name="ping",
                        permissions=[ToolPermissionLevel.READ, ToolPermissionLevel.EXECUTE],
                    )
                ],
            ),
        ]
    )
    catalog_path.write_text(json.dumps(catalog.model_dump(mode="json")), encoding="utf-8")
    runtime = ToolRuntime(
        mcp_catalog_path=catalog_path,
        settings=type("S", (), {"tool_allow_execute": True})(),
    )
    await runtime.start()
    names = {t.name for t in runtime.list_tools(source=ToolSource.MCP)}
    assert any(n.endswith("ping") for n in names)
    assert "mcp.off.tool" not in names
    await runtime.stop()


@pytest.mark.asyncio
async def test_missing_catalog_loads_empty(tmp_path: Path) -> None:
    discovery = MCPDiscovery(tmp_path / "missing.json")
    catalog = discovery.load()
    assert catalog.servers == []
    registry = ToolRegistry()
    registrar = MCPRegistrar(registry, discovery)
    stats = await registrar.reload_async()
    assert stats["added"] == 0
    assert stats["servers"] == 0


@pytest.mark.asyncio
async def test_missing_command_skips_server(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.json"
    catalog = MCPCatalog(
        servers=[
            MCPServerDescriptor(
                name="ghost",
                enabled=True,
                transport="stdio",
                command="emily-mcp-does-not-exist-xyz",
                args=[],
                tools=[],
            )
        ]
    )
    catalog_path.write_text(json.dumps(catalog.model_dump(mode="json")), encoding="utf-8")
    runtime = ToolRuntime(mcp_catalog_path=catalog_path)
    await runtime.start()
    assert runtime.list_tools(source=ToolSource.MCP) == []
    await runtime.stop()


@pytest.mark.asyncio
async def test_ensure_catalog_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    runtime = ToolRuntime(mcp_catalog_path=path)
    await runtime.start()
    first = path.read_text(encoding="utf-8")
    runtime.discovery.ensure_catalog()
    second = path.read_text(encoding="utf-8")
    assert first == second
    assert json.loads(first)["servers"] == []
    await runtime.stop()
