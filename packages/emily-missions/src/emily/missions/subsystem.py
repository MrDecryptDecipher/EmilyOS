"""Kernel subsystem for mission runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from emily.core.types.common import HealthStatus, SubsystemState
from emily.kernel.context import DefaultKernelContext
from emily.kernel.subsystem import BaseSubsystem
from emily.missions.runtime import MissionRuntime


class MissionsSubsystem(BaseSubsystem):
    name = "missions"
    startup_priority = 30
    shutdown_priority = 30

    def __init__(self, missions_dir: Path | str | None = None) -> None:
        super().__init__()
        self.missions_dir = Path(missions_dir or "data/missions")
        self.runtime: MissionRuntime | None = None

    async def on_start(self, ctx: Any) -> None:
        if not isinstance(ctx, DefaultKernelContext):
            raise TypeError("MissionsSubsystem requires DefaultKernelContext")
        self.runtime = MissionRuntime.create_default(
            missions_dir=self.missions_dir,
            provider_router=ctx.provider_router,
            use_llm_planner=bool(ctx.settings.mission_llm_planner),
            event_bus=ctx.event_bus,
            logger=ctx.logger,
            checkpoint_path=self.missions_dir / "checkpoints.sqlite",
        )
        ctx.mission_runtime = self.runtime
        ctx.logger.info("missions subsystem started", root=str(self.missions_dir))

    async def on_stop(self, ctx: Any) -> None:
        if isinstance(ctx, DefaultKernelContext):
            ctx.logger.info("missions subsystem stopped")
            ctx.mission_runtime = None
        self.runtime = None

    async def health(self) -> HealthStatus:
        return HealthStatus(
            name=self.name,
            healthy=self._state == SubsystemState.RUNNING and self.runtime is not None,
            state=self._state,
            message="ready" if self.runtime is not None else "not initialized",
        )
