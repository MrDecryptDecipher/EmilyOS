"""Integration: providers subsystem boots with kernel."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from emily.config.settings import EmilySettings
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.providers.subsystem import ProvidersSubsystem


@pytest.mark.asyncio
async def test_providers_subsystem_attaches_router() -> None:
    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        nvidia_api_key=SecretStr(""),
        routesme_api_key=SecretStr(""),
        _env_file=None,
    )
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ProvidersSubsystem())
    ctx = await kernel.start()
    try:
        assert ctx.provider_router is not None
        assert "nvidia" in ctx.provider_router.list_providers()
        report = await kernel.health()
        names = {s["name"] for s in report["subsystems"]}
        assert "providers" in names
    finally:
        await kernel.stop()
        assert ctx.provider_router is None
