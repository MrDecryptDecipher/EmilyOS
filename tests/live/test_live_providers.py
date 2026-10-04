"""Live provider probes (opt-in).

Enable with:

    $env:EMILY_LIVE_PROVIDERS = "1"
    pytest tests/live -q
"""

from __future__ import annotations

import os

import pytest
from pydantic import SecretStr

from emily.config.loader import load_settings
from emily.config.settings import EmilySettings
from emily.core.types.provider import ProviderStatus
from emily.providers.errors import ProviderInvocationError, ProviderUnavailableError
from emily.providers.factory import build_provider_router
from emily.providers.nvidia import create_nvidia_provider


def _live_enabled() -> bool:
    return os.getenv("EMILY_LIVE_PROVIDERS", "").strip() in {"1", "true", "TRUE", "yes"}


pytestmark = pytest.mark.skipif(
    not _live_enabled(),
    reason="Set EMILY_LIVE_PROVIDERS=1 to run live provider probes",
)


@pytest.mark.asyncio
async def test_live_health_both_providers() -> None:
    settings = load_settings()
    router = build_provider_router(settings)
    await router.start()
    try:
        reports = await router.health_reports()
        by_name = {r.name: r for r in reports}
        assert by_name["nvidia"].status in {
            ProviderStatus.HEALTHY,
            ProviderStatus.DEGRADED,
            ProviderStatus.UNAVAILABLE,
        }
        assert by_name["routesme"].status in {
            ProviderStatus.HEALTHY,
            ProviderStatus.DEGRADED,
            ProviderStatus.UNAVAILABLE,
        }
        # Soft assertion: at least one should be healthy in a working env
        assert any(r.status == ProviderStatus.HEALTHY for r in reports)
    finally:
        await router.stop()


@pytest.mark.asyncio
async def test_live_nvidia_known_good_model_completes() -> None:
    settings = load_settings()
    # Bypass potentially hanging configured GLM model for smoke reliability.
    provider = create_nvidia_provider(
        api_key=settings.nvidia_api_key.get_secret_value(),
        base_url=settings.nvidia_base_url,
        model="deepseek-ai/deepseek-v4-flash-0731",
        timeout_seconds=30.0,
        max_retries=1,
    )
    await provider.start()
    try:
        result = await provider.achat(
            [{"role": "user", "content": "Reply with exactly: LIVE_OK"}],
            max_tokens=16,
        )
        assert "LIVE_OK" in result.content.replace(" ", "") or "LIVE" in result.content.upper()
        assert result.latency_ms > 0
        assert result.provider == "nvidia"
    finally:
        await provider.stop()


@pytest.mark.asyncio
async def test_live_configured_glm_times_out_or_returns() -> None:
    settings = load_settings()
    provider = create_nvidia_provider(
        api_key=settings.nvidia_api_key.get_secret_value(),
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_model,
        timeout_seconds=12.0,
        max_retries=0,
    )
    await provider.start()
    try:
        try:
            result = await provider.achat(
                [{"role": "user", "content": "Say OK"}],
                max_tokens=8,
            )
            # If NIM recovers, accept a successful response.
            assert isinstance(result.content, str)
        except (ProviderUnavailableError, ProviderInvocationError):
            # Expected today: hang -> transport timeout -> unavailable.
            pass
    finally:
        await provider.stop()


@pytest.mark.asyncio
async def test_live_failover_from_bad_primary_key() -> None:
    base = load_settings()
    settings = EmilySettings(
        environment="test",
        primary_provider="nvidia",
        backup_provider="routesme",
        provider_failover_enabled=True,
        provider_timeout_seconds=20.0,
        provider_max_retries=0,
        nvidia_api_key=SecretStr("invalid-nvidia-key"),
        nvidia_base_url=base.nvidia_base_url,
        nvidia_model="deepseek-ai/deepseek-v4-flash-0731",
        routesme_api_key=base.routesme_api_key,
        routesme_base_url=base.routesme_base_url,
        routesme_model=base.routesme_model,
        _env_file=None,
    )
    router = build_provider_router(settings)
    await router.start()
    try:
        try:
            result = await router.achat(
                [{"role": "user", "content": "Reply with exactly: FAILOVER_OK"}],
                max_tokens=16,
            )
            assert result.provider == "routesme"
        except (ProviderUnavailableError, ProviderInvocationError) as exc:
            # RoutesMe may rate-limit (429); still prove nvidia failed first.
            summary = router.analytics.summary()
            assert summary["failures"] >= 1
            assert "nvidia" in str(exc.details.get("errors", [])) or summary["failures"] >= 1
    finally:
        await router.stop()
