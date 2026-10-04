"""Tool and MCP domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from emily.core.ids import new_id, new_tool_id
from emily.core.types.tool import ToolPermissionLevel


class ToolSource(StrEnum):
    BUILTIN = "builtin"
    MCP = "mcp"
    PLUGIN = "plugin"


class ToolSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    title: str
    description: str = ""
    version: str = "0.1.0"
    permissions: list[ToolPermissionLevel] = Field(default_factory=lambda: [ToolPermissionLevel.READ])
    source: ToolSource = ToolSource.BUILTIN
    server: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tool_id: str = Field(default_factory=new_tool_id)
    enabled: bool = True


class CapabilityToken(BaseModel):
    """Capability isolation token — grants a subset of permission levels."""

    model_config = ConfigDict(extra="forbid")

    token_id: str = Field(default_factory=lambda: new_id("cap"))
    granted: list[ToolPermissionLevel] = Field(default_factory=list)
    label: str = "default"
    expires_at: datetime | None = None

    def grants(self) -> frozenset[ToolPermissionLevel]:
        return frozenset(self.granted)

    def is_expired(self, *, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        current = now or datetime.now(UTC)
        return current >= self.expires_at


class ToolInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    capabilities: CapabilityToken | None = None
    timeout_seconds: float | None = None
    caller: str = "cli"


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    success: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    denied: bool = False
    latency_ms: float = 0.0
    permissions_used: list[ToolPermissionLevel] = Field(default_factory=list)


class MCPToolDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    permissions: list[ToolPermissionLevel] = Field(
        default_factory=lambda: [ToolPermissionLevel.READ]
    )
    input_schema: dict[str, Any] = Field(default_factory=dict)
    version: str = "0.1.0"


class MCPServerDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    transport: str = "stdio"
    command: str = ""
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    enabled: bool = True
    tools: list[MCPToolDescriptor] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MCPCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    servers: list[MCPServerDescriptor] = Field(default_factory=list)
    version: str = "1"
