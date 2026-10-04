"""Kernel subsystem for tools & MCP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from emily.core.types.common import HealthStatus, SubsystemState
from emily.kernel.context import DefaultKernelContext
from emily.kernel.subsystem import BaseSubsystem
from emily.tools.runtime import ToolRuntime


class ToolsSubsystem(BaseSubsystem):
    name = "tools"
    startup_priority = 28
    shutdown_priority = 32

    def __init__(self, *, mcp_catalog_path: Path | str | None = None) -> None:
        super().__init__()
        self.runtime: ToolRuntime | None = None
        self._catalog_override = Path(mcp_catalog_path) if mcp_catalog_path is not None else None
        self._disabled = False

    async def on_start(self, ctx: Any) -> None:
        if not isinstance(ctx, DefaultKernelContext):
            raise TypeError("ToolsSubsystem requires DefaultKernelContext")
        if not bool(getattr(ctx.settings, "tools_enabled", True)):
            self._disabled = True
            ctx.logger.info("tools subsystem skipped (disabled)")
            return

        catalog = self._catalog_override or Path(
            getattr(ctx.settings, "mcp_catalog_path", Path("data/mcp/catalog.json"))
        )
        timeout = float(getattr(ctx.settings, "tool_timeout_seconds", 15.0))
        self.runtime = ToolRuntime(
            settings=ctx.settings,
            event_bus=ctx.event_bus,
            mcp_catalog_path=catalog,
            default_timeout_seconds=timeout,
        )
        await self.runtime.start()
        ctx.tool_runtime = self.runtime
        ctx.extras["tool_runtime"] = self.runtime
        stats = self.runtime.stats()
        ctx.logger.info(
            "tools subsystem started",
            tools=stats["tools_total"],
            mcp_servers=stats["mcp_servers"],
            catalog=str(catalog),
        )

    async def on_stop(self, ctx: Any) -> None:
        if self.runtime is not None:
            await self.runtime.stop()
        if isinstance(ctx, DefaultKernelContext):
            stats = self.runtime.stats() if self.runtime is not None else {}
            ctx.logger.info("tools subsystem stopped", stats=stats)
            ctx.tool_runtime = None
            ctx.extras.pop("tool_runtime", None)
        self.runtime = None

    async def health(self) -> HealthStatus:
        if self._disabled:
            return HealthStatus(
                name=self.name,
                healthy=True,
                state=self._state,
                message="disabled",
                details={"tools_total": 0, "mcp_servers": 0},
            )
        total = 0
        mcp_servers = 0
        if self.runtime is not None:
            stats = self.runtime.stats()
            total = int(stats["tools_total"])
            mcp_servers = int(stats["mcp_servers"])
        return HealthStatus(
            name=self.name,
            healthy=self._state == SubsystemState.RUNNING and self.runtime is not None,
            state=self._state,
            message="ready" if self.runtime is not None else "not initialized",
            details={"tools_total": total, "mcp_servers": mcp_servers},
        )
