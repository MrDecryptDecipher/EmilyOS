"""Kernel subsystem for desktop runtime."""

from __future__ import annotations

from typing import Any

from emily.core.types.common import HealthStatus, SubsystemState
from emily.desktop.runtime import DesktopRuntime
from emily.desktop.tools import register_desktop_tools
from emily.kernel.context import DefaultKernelContext
from emily.kernel.subsystem import BaseSubsystem


class DesktopSubsystem(BaseSubsystem):
    name = "desktop"
    startup_priority = 29
    shutdown_priority = 31

    def __init__(self) -> None:
        super().__init__()
        self.runtime: DesktopRuntime | None = None
        self._disabled = False
        self._tool_names: list[str] = []

    async def on_start(self, ctx: Any) -> None:
        if not isinstance(ctx, DefaultKernelContext):
            raise TypeError("DesktopSubsystem requires DefaultKernelContext")
        if not bool(getattr(ctx.settings, "desktop_enabled", True)):
            self._disabled = True
            ctx.logger.info("desktop subsystem skipped (disabled)")
            return

        self.runtime = DesktopRuntime(
            settings=ctx.settings,
            event_bus=ctx.event_bus,
            logger=ctx.logger,
        )
        await self.runtime.start()
        ctx.desktop_runtime = self.runtime
        ctx.extras["desktop_runtime"] = self.runtime

        tool_runtime = getattr(ctx, "tool_runtime", None)
        if tool_runtime is not None and bool(getattr(ctx.settings, "desktop_register_tools", True)):
            self._tool_names = register_desktop_tools(tool_runtime.registry, self.runtime)

        stats = self.runtime.stats()
        ctx.logger.info(
            "desktop subsystem started",
            backend=stats["backend"],
            desktop_control=stats["desktop_control"],
            tools=len(self._tool_names),
        )

    async def on_stop(self, ctx: Any) -> None:
        if self.runtime is not None:
            await self.runtime.stop()
        if isinstance(ctx, DefaultKernelContext):
            stats = self.runtime.stats() if self.runtime is not None else {}
            ctx.logger.info("desktop subsystem stopped", stats=stats)
            ctx.desktop_runtime = None
            ctx.extras.pop("desktop_runtime", None)
        self.runtime = None
        self._tool_names = []

    async def health(self) -> HealthStatus:
        if self._disabled:
            return HealthStatus(
                name=self.name,
                healthy=True,
                state=self._state,
                message="disabled",
                details={"backend": "none", "actions": 0},
            )
        details: dict[str, Any] = {"backend": "none", "actions": 0, "tools": len(self._tool_names)}
        if self.runtime is not None:
            details.update(self.runtime.stats())
            details["tools"] = len(self._tool_names)
        return HealthStatus(
            name=self.name,
            healthy=self._state == SubsystemState.RUNNING and self.runtime is not None,
            state=self._state,
            message="ready" if self.runtime is not None else "not initialized",
            details=details,
        )
