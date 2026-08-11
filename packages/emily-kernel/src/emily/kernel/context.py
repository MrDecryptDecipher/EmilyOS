"""Kernel context passed to subsystems."""

from __future__ import annotations

from dataclasses import dataclass
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

    @property
    def config(self) -> EmilySettings:
        return self.settings

    @property
    def event_bus(self) -> EventBusPort:
        return self.bus

    def get_extra(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
