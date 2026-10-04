"""MCP catalog discovery and live stdio registration."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from emily.core.types.tool import ToolPermissionLevel
from emily.tools.errors import ToolError
from emily.tools.mcp_client import MCPClientError, StdioMCPClient
from emily.tools.models import (
    MCPCatalog,
    MCPServerDescriptor,
    MCPToolDescriptor,
    ToolSource,
    ToolSpec,
)
from emily.tools.registry import ToolHandler, ToolRegistry

_log = logging.getLogger("emily.tools.mcp")


class MCPDiscovery:
    """Loads MCP server/tool descriptors from a JSON catalog file."""

    def __init__(self, catalog_path: Path | str) -> None:
        self.catalog_path = Path(catalog_path)
        self._catalog = MCPCatalog()

    @property
    def catalog(self) -> MCPCatalog:
        return self._catalog

    def load(self) -> MCPCatalog:
        if not self.catalog_path.exists():
            self._catalog = MCPCatalog()
            return self._catalog
        raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        self._catalog = MCPCatalog.model_validate(raw)
        return self._catalog

    def ensure_catalog(self) -> None:
        """Ensure catalog path exists as an empty real catalog (no demo servers)."""
        if self.catalog_path.exists():
            self.load()
            return
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        empty = MCPCatalog(servers=[])
        self.catalog_path.write_text(
            json.dumps(empty.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        self._catalog = empty

    # Back-compat name used by ToolRuntime.
    def ensure_default_catalog(self) -> None:
        self.ensure_catalog()


class MCPRegistrar:
    """Registers live MCP tools (stdio) into the tool registry."""

    def __init__(self, registry: ToolRegistry, discovery: MCPDiscovery) -> None:
        self.registry = registry
        self.discovery = discovery
        self._sessions: dict[str, StdioMCPClient] = {}

    def reload(self) -> dict[str, int]:
        raise RuntimeError("use reload_async() for live MCP registration")

    async def reload_async(self) -> dict[str, int]:
        await self.close()
        catalog = self.discovery.load()
        removed = self.registry.clear_source(ToolSource.MCP)
        added = 0
        servers = 0
        for server in catalog.servers:
            if not server.enabled:
                continue
            if server.transport != "stdio" or not server.command.strip():
                continue
            servers += 1
            client = StdioMCPClient(server.command, list(server.args))
            try:
                await client.start()
                remote_tools = await client.list_tools()
            except Exception as exc:
                await client.close()
                # Fail closed for this server only — do not crash tools subsystem.
                _log.warning(
                    "MCP server unavailable; skipping name=%s command=%s error=%s",
                    server.name,
                    server.command,
                    exc,
                )
                continue
            self._sessions[server.name] = client

            # Prefer live discovery; fall back to catalog descriptors if list is empty.
            descriptors = remote_tools or [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.input_schema,
                }
                for t in server.tools
            ]
            for tool in descriptors:
                name = str(tool.get("name") or "")
                if not name:
                    continue
                desc = str(tool.get("description") or "")
                schema = tool.get("inputSchema") or tool.get("input_schema") or {}
                if not isinstance(schema, dict):
                    schema = {}
                perms = [ToolPermissionLevel.READ, ToolPermissionLevel.EXECUTE]
                catalog_tool = next((t for t in server.tools if t.name == name), None)
                if catalog_tool is not None:
                    perms = list(catalog_tool.permissions) or perms
                spec = ToolSpec(
                    name=name if name.startswith("mcp.") else f"mcp.{server.name}.{name}",
                    title=name,
                    description=desc,
                    permissions=perms,
                    source=ToolSource.MCP,
                    server=server.name,
                    input_schema=dict(schema),
                    metadata={
                        "transport": server.transport,
                        "command": server.command,
                        "remote_name": name,
                    },
                )
                self.registry.register(spec, _make_live_handler(client, name))
                added += 1
        return {"removed": removed, "added": added, "servers": servers}

    async def close(self) -> None:
        sessions = list(self._sessions.values())
        self._sessions.clear()
        for client in sessions:
            await client.close()


def _make_live_handler(client: StdioMCPClient, remote_name: str) -> ToolHandler:
    async def _handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        try:
            result = await client.call_tool(remote_name, dict(arguments))
        except MCPClientError as exc:
            raise ToolError(str(exc), tool_name=remote_name, cause=exc) from exc
        return {
            "server_tool": remote_name,
            "mode": "mcp-live",
            "result": result,
            "ok": True,
        }

    return _handler


# Re-export for typing convenience
__all__ = ["MCPDiscovery", "MCPRegistrar", "MCPServerDescriptor", "MCPToolDescriptor"]
