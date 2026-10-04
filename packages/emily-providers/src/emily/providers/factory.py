"""Build provider router from Emily settings."""

from __future__ import annotations

from emily.config.settings import EmilySettings
from emily.providers.adapter import OpenAICompatibleProvider
from emily.providers.analytics import ProviderAnalytics
from emily.providers.errors import ProviderInvocationError
from emily.providers.nvidia import create_nvidia_provider
from emily.providers.router import ProviderRouter
from emily.providers.routesme import create_routesme_provider


def build_provider_router(
    settings: EmilySettings,
    *,
    analytics: ProviderAnalytics | None = None,
) -> ProviderRouter:
    providers: dict[str, OpenAICompatibleProvider] = {}

    nvidia_key = settings.nvidia_api_key.get_secret_value().strip()
    routesme_key = settings.routesme_api_key.get_secret_value().strip()

    providers["nvidia"] = create_nvidia_provider(
        api_key=nvidia_key,
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_model,
        timeout_seconds=settings.provider_timeout_seconds,
        max_retries=settings.provider_max_retries,
    )
    providers["routesme"] = create_routesme_provider(
        api_key=routesme_key,
        base_url=settings.routesme_base_url,
        model=settings.routesme_model,
        timeout_seconds=settings.provider_timeout_seconds,
        max_retries=settings.provider_max_retries,
    )

    primary = settings.primary_provider
    backup = settings.backup_provider
    if primary not in providers:
        raise ProviderInvocationError(
            f"unknown primary provider {primary!r}",
            provider=primary,
            details={"available": sorted(providers)},
        )

    return ProviderRouter(
        providers,
        primary=primary,
        backup=backup if backup in providers else None,
        failover_enabled=settings.provider_failover_enabled,
        analytics=analytics or ProviderAnalytics(),
    )
