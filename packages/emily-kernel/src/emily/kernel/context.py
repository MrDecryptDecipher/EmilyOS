"""Kernel context passed to subsystems."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from emily.config.settings import EmilySettings
from emily.core.protocols.event_bus import EventBusPort
from emily.core.protocols.observability import LoggerPort, MetricsPort, TracerPort


@dataclass(slots=True)
class DefaultKernelContext:
    settings: EmilySettings
    bus: EventBusPort
    logger: LoggerPort
    metrics: MetricsPort
    tracer: TracerPort
    provider_router: Any | None = None
    provider_analytics: Any | None = None
    mission_runtime: Any | None = None
    agent_supervisor: Any | None = None
    memory_runtime: Any | None = None
    tool_runtime: Any | None = None
    desktop_runtime: Any | None = None
    browser_runtime: Any | None = None
    voice_runtime: Any | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def config(self) -> EmilySettings:
        return self.settings

    @property
    def event_bus(self) -> EventBusPort:
        return self.bus

    def get_extra(self, key: str, default: Any = None) -> Any:
        return self.extras.get(key, default)
