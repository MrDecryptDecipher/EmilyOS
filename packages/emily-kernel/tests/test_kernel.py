"""Kernel lifecycle tests."""

from __future__ import annotations

import pytest

from emily.config.settings import EmilySettings
from emily.core.errors import KernelStateError
from emily.core.types.common import HealthStatus, SubsystemState
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.kernel.lifecycle import KernelState


class FlakySubsystem:
    name = "flaky"
    startup_priority = 50
    shutdown_priority = 50

    async def start(self, ctx: object) -> None:
        raise RuntimeError("cannot start")

    async def stop(self, ctx: object) -> None:
        return None

    async def health(self) -> HealthStatus:
        return HealthStatus(name=self.name, healthy=False, state=SubsystemState.FAILED)


@pytest.mark.asyncio
async def test_kernel_boot_and_health(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    settings = EmilySettings(
        app_name="Emily OS Test",
        environment="test",
        log_level="WARNING",
        _env_file=None,
    )
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    ctx = await kernel.start()
    assert kernel.state == KernelState.RUNNING
    assert ctx.settings.app_name == "Emily OS Test"
    report = await kernel.health()
    assert report["healthy"] is True
    await kernel.stop()
    assert kernel.state == KernelState.STOPPED


@pytest.mark.asyncio
async def test_kernel_subsystem_failure() -> None:
    settings = EmilySettings(environment="test", log_level="ERROR", _env_file=None)
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(FlakySubsystem())
    with pytest.raises(KernelStateError):
        await kernel.start()
    assert kernel.state == KernelState.FAILED
