"""Kernel subsystem for voice runtime."""

from __future__ import annotations

from typing import Any

from emily.core.types.common import HealthStatus, SubsystemState
from emily.kernel.context import DefaultKernelContext
from emily.kernel.subsystem import BaseSubsystem
from emily.voice.runtime import VoiceRuntime
from emily.voice.tools import register_voice_tools


class VoiceSubsystem(BaseSubsystem):
    name = "voice"
    startup_priority = 31
    shutdown_priority = 29

    def __init__(self) -> None:
        super().__init__()
        self.runtime: VoiceRuntime | None = None
        self._disabled = False
        self._tool_names: list[str] = []

    async def on_start(self, ctx: Any) -> None:
        if not isinstance(ctx, DefaultKernelContext):
            raise TypeError("VoiceSubsystem requires DefaultKernelContext")
        if not bool(getattr(ctx.settings, "voice_enabled", False)):
            self._disabled = True
            ctx.logger.info("voice subsystem skipped (disabled)")
            return

        self.runtime = VoiceRuntime(
            settings=ctx.settings,
            event_bus=ctx.event_bus,
            logger=ctx.logger,
            provider_router=getattr(ctx, "provider_router", None),
        )
        await self.runtime.start()
        ctx.voice_runtime = self.runtime
        ctx.extras["voice_runtime"] = self.runtime

        tool_runtime = getattr(ctx, "tool_runtime", None)
        if tool_runtime is not None and bool(getattr(ctx.settings, "voice_register_tools", True)):
            self._tool_names = register_voice_tools(tool_runtime.registry, self.runtime)

        stats = self.runtime.stats()
        ctx.logger.info(
            "voice subsystem started",
            backends=stats.get("backends"),
            tools=len(self._tool_names),
        )

    async def on_stop(self, ctx: Any) -> None:
        if self.runtime is not None:
            await self.runtime.stop()
        if isinstance(ctx, DefaultKernelContext):
            stats = self.runtime.stats() if self.runtime is not None else {}
            ctx.logger.info("voice subsystem stopped", stats=stats)
            ctx.voice_runtime = None
            ctx.extras.pop("voice_runtime", None)
        self.runtime = None
        self._tool_names = []

    async def health(self) -> HealthStatus:
        if self._disabled:
            return HealthStatus(
                name=self.name,
                healthy=True,
                state=self._state,
                message="disabled",
                details={"backends": 0, "actions": 0},
            )
        details: dict[str, str | int | float | bool] = {
            "backends": 0,
            "actions": 0,
            "tools": len(self._tool_names),
        }
        if self.runtime is not None:
            stats = self.runtime.stats()
            backends = stats.get("backends") or {}
            available = sum(1 for v in backends.values() if v) if isinstance(backends, dict) else 0
            details = {
                "backends": int(available),
                "actions": int(stats.get("actions", 0)),
                "tools": len(self._tool_names),
                "started": bool(stats.get("started", False)),
                "state": str(stats.get("state", "idle")),
            }
        return HealthStatus(
            name=self.name,
            healthy=self._state == SubsystemState.RUNNING and self.runtime is not None,
            state=self._state,
            message="ready" if self.runtime is not None else "not initialized",
            details=details,
        )
