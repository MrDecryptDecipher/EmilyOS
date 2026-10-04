"""Kernel subsystem for provider fabric lifecycle."""

from __future__ import annotations

from typing import Any

from emily.core.types.common import HealthStatus, SubsystemState
from emily.core.types.provider import ProviderStatus
from emily.events.types import EventTypes
from emily.kernel.context import DefaultKernelContext
from emily.kernel.subsystem import BaseSubsystem
from emily.providers.analytics import ProviderAnalytics
from emily.providers.factory import build_provider_router
from emily.providers.router import ProviderRouter


class ProvidersSubsystem(BaseSubsystem):
    """Registers and manages the provider router inside the kernel."""

    name = "providers"
    startup_priority = 20
    shutdown_priority = 20

    def __init__(self) -> None:
        super().__init__()
        self.router: ProviderRouter | None = None
        self.analytics = ProviderAnalytics()

    async def on_start(self, ctx: Any) -> None:
        if not isinstance(ctx, DefaultKernelContext):
            raise TypeError("ProvidersSubsystem requires DefaultKernelContext")

        self.router = build_provider_router(ctx.settings, analytics=self.analytics)
        await self.router.start()
        ctx.provider_router = self.router
        ctx.provider_analytics = self.analytics

        reports = await self.router.health_reports()
        for report in reports:
            await ctx.event_bus.publish(
                EventTypes.PROVIDER_HEALTH_CHANGED,
                report.model_dump(mode="json"),
                source="providers",
            )
        ctx.logger.info(
            "providers subsystem started",
            primary=ctx.settings.primary_provider,
            backup=ctx.settings.backup_provider,
            providers=self.router.list_providers(),
        )

    async def on_stop(self, ctx: Any) -> None:
        if self.router is not None:
            await self.router.stop()
        if isinstance(ctx, DefaultKernelContext):
            ctx.logger.info(
                "providers subsystem stopped",
                analytics=self.analytics.summary(),
            )
            ctx.provider_router = None
            ctx.provider_analytics = None

    async def health(self) -> HealthStatus:
        if self.router is None:
            return HealthStatus(
                name=self.name,
                healthy=False,
                state=self._state,
                message="router not initialized",
            )
        status = await self.router.health()
        healthy = status in {ProviderStatus.HEALTHY, ProviderStatus.DEGRADED}
        return HealthStatus(
            name=self.name,
            healthy=healthy and self._state == SubsystemState.RUNNING,
            state=self._state,
            message=status.value,
            details={"analytics_calls": int(self.analytics.summary()["calls"])},
        )
