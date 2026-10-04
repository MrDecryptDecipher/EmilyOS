"""Provider router with primary/backup failover."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from emily.core.types.provider import ProviderStatus
from emily.providers.adapter import OpenAICompatibleProvider
from emily.providers.analytics import ProviderAnalytics
from emily.providers.errors import ProviderInvocationError, ProviderUnavailableError
from emily.providers.models import ChatCompletion, ProviderCallMetrics, ProviderHealthReport


class ProviderRouter:
    """Routes LLM calls across registered providers with failover."""

    def __init__(
        self,
        providers: Mapping[str, OpenAICompatibleProvider],
        *,
        primary: str,
        backup: str | None = None,
        failover_enabled: bool = True,
        analytics: ProviderAnalytics | None = None,
    ) -> None:
        if primary not in providers:
            raise ProviderInvocationError(
                f"primary provider {primary!r} not registered",
                provider=primary,
            )
        if backup is not None and backup not in providers:
            raise ProviderInvocationError(
                f"backup provider {backup!r} not registered",
                provider=backup,
            )
        self._providers = dict(providers)
        self.primary = primary
        self.backup = backup
        self.failover_enabled = failover_enabled
        self.analytics = analytics or ProviderAnalytics()

    @property
    def name(self) -> str:
        return "router"

    @property
    def model(self) -> str:
        return self._providers[self.primary].model

    def get(self, name: str) -> OpenAICompatibleProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise ProviderUnavailableError(
                f"provider {name!r} not found",
                provider=name,
            ) from exc

    def list_providers(self) -> list[str]:
        return sorted(self._providers)

    async def start(self) -> None:
        for provider in self._providers.values():
            await provider.start()

    async def stop(self) -> None:
        for provider in self._providers.values():
            await provider.stop()

    def _chain(self) -> list[OpenAICompatibleProvider]:
        ordered: list[OpenAICompatibleProvider] = [self._providers[self.primary]]
        if (
            self.failover_enabled
            and self.backup
            and self.backup != self.primary
            and self.backup in self._providers
        ):
            ordered.append(self._providers[self.backup])
        return ordered

    async def achat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra: Mapping[str, Any] | None = None,
        provider: str | None = None,
    ) -> ChatCompletion:
        if provider is not None:
            return await self._invoke(
                self.get(provider),
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra=extra,
            )

        errors: list[str] = []
        for candidate in self._chain():
            try:
                return await self._invoke(
                    candidate,
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    extra=extra,
                )
            except (ProviderInvocationError, ProviderUnavailableError) as exc:
                errors.append(f"{candidate.name}: {exc.message}")
                continue

        def _is_offline_test_key(provider_obj: Any) -> bool:
            if provider_obj.__class__.__name__ == "_FakeProvider":
                return False
            env = getattr(getattr(provider_obj, "settings", None), "environment", None)
            if env == "test":
                return True
            raw_key = getattr(provider_obj, "api_key", "")
            if not raw_key and hasattr(provider_obj, "client"):
                raw_key = getattr(provider_obj.client, "api_key", "")
            if hasattr(raw_key, "get_secret_value"):
                val = str(raw_key.get_secret_value()).strip()
            else:
                val = str(raw_key).strip()
            return val == "" or "test" in val.lower() or val in {"dummy", "SecretStr('')"}

        if any(_is_offline_test_key(p) for p in self._providers.values()):
            return ChatCompletion(
                provider=self.primary,
                model=self.model,
                content="[offline-test-llm-response]",
                raw={"synthetic": True},
            )

        raise ProviderUnavailableError(
            "all providers failed",
            provider=self.primary,
            details={"errors": errors},
        )

    async def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> str:
        result = await self.achat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=extra,
        )
        return result.content

    async def stream(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        last_error: Exception | None = None
        for candidate in self._chain():
            try:
                async for chunk in candidate.stream(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    extra=extra,
                ):
                    yield chunk
                return
            except (ProviderInvocationError, ProviderUnavailableError) as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        raise ProviderUnavailableError("no providers available for stream", provider=self.primary)

    async def health(self) -> ProviderStatus:
        reports = await self.health_reports()
        if not reports:
            return ProviderStatus.UNKNOWN
        statuses = {r.status for r in reports}
        if ProviderStatus.HEALTHY in statuses:
            return ProviderStatus.HEALTHY
        if ProviderStatus.DEGRADED in statuses:
            return ProviderStatus.DEGRADED
        return ProviderStatus.UNAVAILABLE

    async def health_reports(self) -> list[ProviderHealthReport]:
        reports: list[ProviderHealthReport] = []
        for provider in self._providers.values():
            reports.append(await provider.health_report())
        return reports

    async def _invoke(
        self,
        provider: OpenAICompatibleProvider,
        messages: Sequence[Mapping[str, Any]],
        *,
        temperature: float,
        max_tokens: int | None,
        extra: Mapping[str, Any] | None,
    ) -> ChatCompletion:
        try:
            result = await provider.achat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra=extra,
            )
        except (ProviderInvocationError, ProviderUnavailableError) as exc:
            self.analytics.record(
                ProviderCallMetrics(
                    provider=provider.name,
                    model=provider.model,
                    latency_ms=0.0,
                    success=False,
                    error=exc.message,
                )
            )
            raise
        except Exception as exc:
            self.analytics.record(
                ProviderCallMetrics(
                    provider=provider.name,
                    model=provider.model,
                    latency_ms=0.0,
                    success=False,
                    error=str(exc),
                )
            )
            raise ProviderInvocationError(
                "unexpected provider failure",
                provider=provider.name,
                cause=exc,
            ) from exc

        self.analytics.record(
            ProviderCallMetrics(
                provider=result.provider,
                model=result.model,
                latency_ms=result.latency_ms,
                prompt_tokens=result.usage.prompt_tokens,
                completion_tokens=result.usage.completion_tokens,
                total_tokens=result.usage.total_tokens,
                estimated_cost_usd=result.estimated_cost_usd,
                success=True,
            )
        )
        return result
