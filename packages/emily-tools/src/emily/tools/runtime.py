"""Tool runtime facade."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from emily.tools.builtins import register_builtins
from emily.tools.executor import ToolExecutor
from emily.tools.mcp import MCPDiscovery, MCPRegistrar
from emily.tools.models import CapabilityToken, ToolInvocation, ToolResult, ToolSource, ToolSpec
from emily.tools.policy import PermissionPolicy
from emily.tools.registry import ToolRegistry


class ToolRuntime:
    def __init__(
        self,
        *,
        settings: Any | None = None,
        event_bus: Any | None = None,
        mcp_catalog_path: Path | str | None = None,
        default_timeout_seconds: float = 15.0,
    ) -> None:
        self.registry = ToolRegistry()
        self.policy = PermissionPolicy(settings)
        self.executor = ToolExecutor(
            self.registry,
            self.policy,
            event_bus=event_bus,
            default_timeout_seconds=default_timeout_seconds,
        )
        catalog = Path(mcp_catalog_path or "data/mcp/catalog.json")
        self.discovery = MCPDiscovery(catalog)
        self.mcp = MCPRegistrar(self.registry, self.discovery)
        self._started = False

    async def start(self) -> None:
        register_builtins(self.registry)
        self.discovery.ensure_catalog()
        await self.mcp.reload_async()
        self._started = True

    async def stop(self) -> None:
        await self.mcp.close()
        self._started = False

    async def invoke(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        capabilities: CapabilityToken | None = None,
        caller: str = "runtime",
        timeout_seconds: float | None = None,
    ) -> ToolResult:
        return await self.executor.invoke(
            ToolInvocation(
                tool_name=tool_name,
                arguments=dict(arguments or {}),
                capabilities=capabilities,
                caller=caller,
                timeout_seconds=timeout_seconds,
            )
        )

    def list_tools(self, *, source: ToolSource | None = None) -> list[ToolSpec]:
        return self.registry.list_tools(source=source)

    def reload_mcp(self) -> dict[str, int]:
        raise RuntimeError("use reload_mcp_async() for live MCP reload")

    async def reload_mcp_async(self) -> dict[str, int]:
        result = await self.mcp.reload_async()
        if self.executor.event_bus is not None:
            await self.executor.event_bus.publish(
                "mcp.reloaded",
                result,
                source="tools",
            )
        return result

    def stats(self) -> dict[str, Any]:
        tools = self.registry.list_tools(include_disabled=True)
        by_source: dict[str, int] = {}
        for tool in tools:
            by_source[tool.source.value] = by_source.get(tool.source.value, 0) + 1
        return {
            "tools_total": len(tools),
            "by_source": by_source,
            "mcp_servers": len(self.discovery.catalog.servers),
            "allowed_permissions": sorted(p.value for p in self.policy.allowed_levels()),
        }
