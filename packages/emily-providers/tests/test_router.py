"""Provider router failover tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

import pytest

from emily.core.types.provider import ProviderStatus
from emily.providers.errors import ProviderUnavailableError
from emily.providers.models import ChatCompletion, CompletionUsage, ProviderHealthReport
from emily.providers.router import ProviderRouter


class _FakeProvider:
    def __init__(self, name: str, *, fail: bool = False, content: str = "ok") -> None:
        self.name = name
        self.model = f"{name}-model"
        self.fail = fail
        self.content = content
        self.started = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False

    async def achat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> ChatCompletion:
        if self.fail:
            raise ProviderUnavailableError("down", provider=self.name)
        return ChatCompletion(
            provider=self.name,
            model=self.model,
            content=self.content,
            usage=CompletionUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            latency_ms=12.5,
            estimated_cost_usd=0.0001,
        )

    async def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> str:
        return (await self.achat(messages)).content

    async def stream(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        if self.fail:
            raise ProviderUnavailableError("down", provider=self.name)
        yield self.content

    async def health(self) -> ProviderStatus:
        return ProviderStatus.UNAVAILABLE if self.fail else ProviderStatus.HEALTHY

    async def health_report(self) -> ProviderHealthReport:
        status = await self.health()
        return ProviderHealthReport(
            name=self.name,
            model=self.model,
            status=status,
            latency_ms=1.0,
            message=status.value,
        )


@pytest.mark.asyncio
async def test_router_failover_to_backup() -> None:
    primary = _FakeProvider("nvidia", fail=True)
    backup = _FakeProvider("routesme", content="from-backup")
    router = ProviderRouter(
        {"nvidia": primary, "routesme": backup},  # type: ignore[arg-type]
        primary="nvidia",
        backup="routesme",
        failover_enabled=True,
    )
    result = await router.achat([{"role": "user", "content": "hi"}])
    assert result.content == "from-backup"
    assert result.provider == "routesme"
    assert router.analytics.summary()["failures"] == 1
    assert router.analytics.summary()["successes"] == 1


@pytest.mark.asyncio
async def test_router_all_fail() -> None:
    router = ProviderRouter(
        {
            "nvidia": _FakeProvider("nvidia", fail=True),
            "routesme": _FakeProvider("routesme", fail=True),
        },  # type: ignore[arg-type]
        primary="nvidia",
        backup="routesme",
    )
    with pytest.raises(ProviderUnavailableError):
        await router.achat([{"role": "user", "content": "hi"}])
