"""Factory and pricing unit tests."""

from __future__ import annotations

from pydantic import SecretStr

from emily.config.settings import EmilySettings
from emily.providers.factory import build_provider_router
from emily.providers.pricing import estimate_cost_usd


def test_estimate_cost_known_model() -> None:
    cost = estimate_cost_usd(
        "z-ai/glm-5.2",
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
    )
    assert cost == 2.0


def test_build_router_from_settings() -> None:
    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        primary_provider="nvidia",
        backup_provider="routesme",
        nvidia_api_key=SecretStr("nv-test"),
        routesme_api_key=SecretStr("rm-test"),
        _env_file=None,
    )
    router = build_provider_router(settings)
    assert router.primary == "nvidia"
    assert router.backup == "routesme"
    assert set(router.list_providers()) == {"nvidia", "routesme"}
