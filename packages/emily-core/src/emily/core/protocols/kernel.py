"""Kernel and subsystem ports."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from emily.core.types.common import HealthStatus


@runtime_checkable
class KernelContext(Protocol):
    @property
    def config(self) -> Any: ...

    @property
    def event_bus(self) -> Any: ...

    @property
    def logger(self) -> Any: ...


@runtime_checkable
class Subsystem(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def startup_priority(self) -> int: ...

    @property
    def shutdown_priority(self) -> int: ...

    async def start(self, ctx: KernelContext) -> None: ...

    async def stop(self, ctx: KernelContext) -> None: ...

    async def health(self) -> HealthStatus: ...
