"""Integration depth: providers subsystem health semantics."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from emily.config.settings import EmilySettings
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.providers.subsystem import ProvidersSubsystem


@pytest.mark.asyncio
async def test_providers_health_with_empty_keys_is_unhealthy_message() -> None:
    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        nvidia_api_key=SecretStr(""),
        routesme_api_key=SecretStr(""),
        _env_file=None,
    )
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    subsys = ProvidersSubsystem()
    kernel.register(subsys)
    await kernel.start()
    try:
        health = await subsys.health()
        # Empty keys => UNAVAILABLE => healthy=False for providers subsystem.
        assert health.name == "providers"
        assert health.healthy is False
        assert health.message == "unavailable"
    finally:
        await kernel.stop()
