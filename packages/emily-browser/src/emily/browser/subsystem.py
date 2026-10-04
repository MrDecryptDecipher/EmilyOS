"""Kernel subsystem for browser runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from emily.browser.runtime import BrowserRuntime
from emily.browser.tools import register_browser_tools
from emily.core.types.common import HealthStatus, SubsystemState
from emily.kernel.context import DefaultKernelContext
from emily.kernel.subsystem import BaseSubsystem


class BrowserSubsystem(BaseSubsystem):
    name = "browser"
    startup_priority = 30
    shutdown_priority = 30

    def __init__(self, *, profiles_dir: Path | str | None = None) -> None:
        super().__init__()
        self.runtime: BrowserRuntime | None = None
        self._profiles_override = Path(profiles_dir) if profiles_dir is not None else None
        self._disabled = False
        self._tool_names: list[str] = []

    async def on_start(self, ctx: Any) -> None:
        if not isinstance(ctx, DefaultKernelContext):
            raise TypeError("BrowserSubsystem requires DefaultKernelContext")
        if not bool(getattr(ctx.settings, "browser_enabled", True)):
            self._disabled = True
            ctx.logger.info("browser subsystem skipped (disabled)")
            return

        profiles = self._profiles_override or Path(
            getattr(ctx.settings, "browser_profiles_directory", Path("data/browser/profiles"))
        )
        self.runtime = BrowserRuntime(
            settings=ctx.settings,
            event_bus=ctx.event_bus,
            logger=ctx.logger,
            profiles_root=profiles,
        )
        await self.runtime.start()
        ctx.browser_runtime = self.runtime
        ctx.extras["browser_runtime"] = self.runtime

        tool_runtime = getattr(ctx, "tool_runtime", None)
        if tool_runtime is not None and bool(getattr(ctx.settings, "browser_register_tools", True)):
            self._tool_names = register_browser_tools(tool_runtime.registry, self.runtime)

        stats = self.runtime.stats()
        ctx.logger.info(
            "browser subsystem started",
            profile=stats["profile"],
            headless=stats["headless"],
            tools=len(self._tool_names),
        )

    async def on_stop(self, ctx: Any) -> None:
        if self.runtime is not None:
            await self.runtime.stop()
        if isinstance(ctx, DefaultKernelContext):
            stats = self.runtime.stats() if self.runtime is not None else {}
            ctx.logger.info("browser subsystem stopped", stats=stats)
            ctx.browser_runtime = None
            ctx.extras.pop("browser_runtime", None)
        self.runtime = None
        self._tool_names = []

    async def health(self) -> HealthStatus:
        if self._disabled:
            return HealthStatus(
                name=self.name,
                healthy=True,
                state=self._state,
                message="disabled",
                details={"backend": "none", "open": False},
            )
        details: dict[str, Any] = {"backend": "none", "open": False, "tools": len(self._tool_names)}
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
