"""Executive Kernel implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from emily.config.loader import load_settings
from emily.config.settings import EmilySettings
from emily.core.errors import KernelStateError
from emily.core.protocols.kernel import Subsystem
from emily.core.types.common import HealthStatus, SubsystemState
from emily.events.bus import InProcessEventBus
from emily.events.types import EventTypes
from emily.kernel.context import DefaultKernelContext
from emily.kernel.lifecycle import KernelState
from emily.observability.logging import StructuredLogger, configure_logging
from emily.observability.metrics import InMemoryMetrics
from emily.observability.tracing import NoOpTracer


@dataclass
class ExecutiveKernel:
    """Process control plane for Emily OS."""

    settings: EmilySettings | None = None
    bus: InProcessEventBus = field(default_factory=InProcessEventBus)
    logger: StructuredLogger | None = None
    metrics: InMemoryMetrics = field(default_factory=InMemoryMetrics)
    tracer: NoOpTracer = field(default_factory=NoOpTracer)
    _state: KernelState = KernelState.CREATED
    _subsystems: list[Subsystem] = field(default_factory=list)
    _ctx: DefaultKernelContext | None = None
    _failure: str | None = None

    @property
    def state(self) -> KernelState:
        return self._state

    def register(self, subsystem: Subsystem) -> None:
        if self._state not in {KernelState.CREATED, KernelState.STOPPED}:
            raise KernelStateError(
                "subsystems can only be registered before start or after stop",
                details={"state": self._state.value},
            )
        self._subsystems.append(subsystem)

    def get_subsystem(self, name: str) -> Any | None:
        for s in self._subsystems:
            if getattr(s, "name", None) == name:
                return s
        return None

    async def start(self) -> DefaultKernelContext:
        if self._state == KernelState.RUNNING:
            if self._ctx is None:
                raise KernelStateError("kernel running without context")
            return self._ctx
        if self._state not in {KernelState.CREATED, KernelState.STOPPED}:
            raise KernelStateError(
                "invalid transition to start",
                details={"state": self._state.value},
            )

        self._state = KernelState.INITIALIZING
        try:
            settings = self.settings or load_settings()
            self.settings = settings
            logger = self.logger or configure_logging(settings.log_level)
            self.logger = logger
            ctx = DefaultKernelContext(
                settings=settings,
                bus=self.bus,
                logger=logger,
                metrics=self.metrics,
                tracer=self.tracer,
            )
            self._ctx = ctx

            await self.bus.start()
            await self.bus.publish(
                EventTypes.KERNEL_BOOTSTRAP_STARTED,
                {"environment": settings.environment},
                source="kernel",
            )
            await self.bus.publish(
                EventTypes.CONFIG_LOADED,
                {
                    "app_name": settings.app_name,
                    "app_version": settings.app_version,
                    "providers": settings.provider_summary(),
                },
                source="kernel",
            )

            for subsystem in sorted(self._subsystems, key=lambda s: s.startup_priority):
                try:
                    await subsystem.start(ctx)
                    await self.bus.publish(
                        EventTypes.KERNEL_SUBSYSTEM_STARTED,
                        {"name": subsystem.name},
                        source="kernel",
                    )
                    self.metrics.counter("kernel.subsystem.start", tags={"name": subsystem.name})
                except Exception as exc:
                    self._state = KernelState.FAILED
                    self._failure = str(exc)
                    await self.bus.publish(
                        EventTypes.KERNEL_SUBSYSTEM_FAILED,
                        {"name": subsystem.name, "error": str(exc)},
                        source="kernel",
                    )
                    logger.exception("subsystem start failed", subsystem=subsystem.name)
                    raise KernelStateError(
                        f"subsystem {subsystem.name!r} failed to start",
                        details={"error": str(exc)},
                    ) from exc

            self._state = KernelState.RUNNING
            await self.bus.publish(
                EventTypes.KERNEL_BOOTSTRAP_COMPLETED,
                {"subsystem_count": len(self._subsystems)},
                source="kernel",
            )
            logger.info(
                "kernel running",
                app=settings.app_name,
                version=settings.app_version,
                subsystems=len(self._subsystems),
            )
            return ctx
        except Exception:
            if self._state != KernelState.FAILED:
                self._state = KernelState.FAILED
            raise

    async def stop(self) -> None:
        if self._state in {KernelState.STOPPED, KernelState.CREATED}:
            return
        if self._ctx is None:
            self._state = KernelState.STOPPED
            return

        self._state = KernelState.DRAINING
        ctx = self._ctx
        assert self.logger is not None
        await self.bus.publish(EventTypes.KERNEL_SHUTDOWN_STARTED, {}, source="kernel")

        for subsystem in sorted(self._subsystems, key=lambda s: s.shutdown_priority):
            try:
                await subsystem.stop(ctx)
                await self.bus.publish(
                    EventTypes.KERNEL_SUBSYSTEM_STOPPED,
                    {"name": subsystem.name},
                    source="kernel",
                )
            except Exception as exc:
                self.logger.error(
                    "subsystem stop failed",
                    subsystem=subsystem.name,
                    error=str(exc),
                )

        await self.bus.publish(EventTypes.KERNEL_SHUTDOWN_COMPLETED, {}, source="kernel")
        await self.bus.stop()
        self._state = KernelState.STOPPED
        self.logger.info("kernel stopped")

    async def health(self) -> dict[str, Any]:
        reports: list[HealthStatus] = []
        for subsystem in self._subsystems:
            reports.append(await subsystem.health())
        return {
            "kernel_state": self._state.value,
            "healthy": self._state == KernelState.RUNNING and all(r.healthy for r in reports),
            "failure": self._failure,
            "subsystems": [r.model_dump(mode="json") for r in reports],
            "app": {
                "name": self.settings.app_name if self.settings else None,
                "version": self.settings.app_version if self.settings else None,
                "environment": self.settings.environment if self.settings else None,
            },
        }


class HeartbeatSubsystem:
    """Minimal built-in subsystem proving registry wiring."""

    name = "heartbeat"
    startup_priority = 10
    shutdown_priority = 10

    def __init__(self) -> None:
        self._state = SubsystemState.CREATED

    async def start(self, ctx: Any) -> None:
        self._state = SubsystemState.RUNNING
        ctx.logger.info("heartbeat subsystem started")

    async def stop(self, ctx: Any) -> None:
        self._state = SubsystemState.STOPPED
        ctx.logger.info("heartbeat subsystem stopped")

    async def health(self) -> HealthStatus:
        return HealthStatus(
            name=self.name,
            healthy=self._state == SubsystemState.RUNNING,
            state=self._state,
        )
