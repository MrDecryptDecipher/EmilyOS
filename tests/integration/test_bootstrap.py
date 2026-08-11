"""Integration: kernel + bus + config smoke."""

from __future__ import annotations

import pytest

from emily.config.settings import EmilySettings
from emily.events.types import EventTypes
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem


@pytest.mark.asyncio
async def test_end_to_end_bootstrap_emits_events() -> None:
    seen: list[str] = []

    async def capture(event_type: str, _payload: dict[str, object]) -> None:
        seen.append(event_type)

    settings = EmilySettings(environment="test", log_level="ERROR", _env_file=None)
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    # Subscribe before start; bus start publishes BUS_STARTED.
    kernel.bus.subscribe("kernel.*", capture)
    kernel.bus.subscribe("events.*", capture)
    kernel.bus.subscribe("config.*", capture)

    await kernel.start()
    await kernel.stop()

    assert EventTypes.KERNEL_BOOTSTRAP_STARTED in seen
    assert EventTypes.KERNEL_BOOTSTRAP_COMPLETED in seen
    assert EventTypes.KERNEL_SHUTDOWN_COMPLETED in seen
