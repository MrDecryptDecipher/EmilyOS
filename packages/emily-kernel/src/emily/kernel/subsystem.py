"""Base subsystem helper."""

from __future__ import annotations

from emily.core.protocols.kernel import KernelContext
from emily.core.types.common import HealthStatus, SubsystemState


class BaseSubsystem:
    """Convenience base for subsystems (not required; protocols are enough)."""

    name: str = "unnamed"
    startup_priority: int = 100
    shutdown_priority: int = 100

    def __init__(self) -> None:
        self._state = SubsystemState.CREATED

    async def start(self, ctx: KernelContext) -> None:
        self._state = SubsystemState.INITIALIZING
        await self.on_start(ctx)
        self._state = SubsystemState.RUNNING

    async def stop(self, ctx: KernelContext) -> None:
        self._state = SubsystemState.DRAINING
        await self.on_stop(ctx)
        self._state = SubsystemState.STOPPED

    async def health(self) -> HealthStatus:
        return HealthStatus(
            name=self.name,
            healthy=self._state == SubsystemState.RUNNING,
            state=self._state,
            message=self._state.value,
        )

    async def on_start(self, ctx: KernelContext) -> None:
        return None

    async def on_stop(self, ctx: KernelContext) -> None:
        return None
