"""Extended router behavior tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

import pytest

from emily.core.types.provider import ProviderStatus
from emily.providers.errors import ProviderInvocationError, ProviderUnavailableError
from emily.providers.models import ChatCompletion, CompletionUsage, ProviderHealthReport
from emily.providers.router import ProviderRouter


class _FakeProvider:
    def __init__(
        self,
        name: str,
        *,
        fail: bool = False,
        content: str = "ok",
        status: ProviderStatus = ProviderStatus.HEALTHY,
        stream_fail: bool = False,
    ) -> None:
        self.name = name
        self.model = f"{name}-model"
        self.fail = fail
        self.content = content
        self.status = status
        self.stream_fail = stream_fail
        self.calls = 0

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def achat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> ChatCompletion:
        self.calls += 1
        if self.fail:
            raise ProviderUnavailableError("down", provider=self.name)
        return ChatCompletion(
            provider=self.name,
            model=self.model,
            content=self.content,
            usage=CompletionUsage(prompt_tokens=2, completion_tokens=3, total_tokens=5),
            latency_ms=8.0,
            estimated_cost_usd=0.0002,
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
        if self.stream_fail or self.fail:
            raise ProviderUnavailableError("stream down", provider=self.name)
        yield "A"
        yield "B"

    async def health(self) -> ProviderStatus:
        return self.status

    async def health_report(self) -> ProviderHealthReport:
        status = await self.health()
        return ProviderHealthReport(
            name=self.name,
            model=self.model,
            status=status,
            latency_ms=1.5,
            message=status.value,
        )


@pytest.mark.asyncio
async def test_force_provider_bypasses_failover() -> None:
    primary = _FakeProvider("nvidia", fail=True)
    backup = _FakeProvider("routesme", content="backup")
    router = ProviderRouter(
        {"nvidia": primary, "routesme": backup},  # type: ignore[arg-type]
        primary="nvidia",
        backup="routesme",
    )
    with pytest.raises(ProviderUnavailableError):
        await router.achat([{"role": "user", "content": "hi"}], provider="nvidia")
    assert backup.calls == 0


@pytest.mark.asyncio
async def test_failover_disabled_does_not_use_backup() -> None:
    primary = _FakeProvider("nvidia", fail=True)
    backup = _FakeProvider("routesme", content="backup")
    router = ProviderRouter(
        {"nvidia": primary, "routesme": backup},  # type: ignore[arg-type]
        primary="nvidia",
        backup="routesme",
        failover_enabled=False,
    )
    with pytest.raises(ProviderUnavailableError, match="all providers failed"):
        await router.achat([{"role": "user", "content": "hi"}])
    assert backup.calls == 0


@pytest.mark.asyncio
async def test_complete_delegates_to_achat() -> None:
    router = ProviderRouter(
        {"nvidia": _FakeProvider("nvidia", content="hello")},  # type: ignore[arg-type]
        primary="nvidia",
    )
    assert await router.complete([{"role": "user", "content": "hi"}]) == "hello"


@pytest.mark.asyncio
async def test_stream_failover() -> None:
    router = ProviderRouter(
        {
            "nvidia": _FakeProvider("nvidia", stream_fail=True),
            "routesme": _FakeProvider("routesme"),
        },  # type: ignore[arg-type]
        primary="nvidia",
        backup="routesme",
    )
    chunks = [c async for c in router.stream([{"role": "user", "content": "hi"}])]
    assert chunks == ["A", "B"]


@pytest.mark.asyncio
async def test_health_aggregation_states() -> None:
    healthy = ProviderRouter(
        {"nvidia": _FakeProvider("nvidia", status=ProviderStatus.HEALTHY)},  # type: ignore[arg-type]
        primary="nvidia",
    )
    assert await healthy.health() == ProviderStatus.HEALTHY

    degraded = ProviderRouter(
        {"nvidia": _FakeProvider("nvidia", status=ProviderStatus.DEGRADED)},  # type: ignore[arg-type]
        primary="nvidia",
    )
    assert await degraded.health() == ProviderStatus.DEGRADED

    down = ProviderRouter(
        {"nvidia": _FakeProvider("nvidia", status=ProviderStatus.UNAVAILABLE)},  # type: ignore[arg-type]
        primary="nvidia",
    )
    assert await down.health() == ProviderStatus.UNAVAILABLE


def test_invalid_primary_raises() -> None:
    with pytest.raises(ProviderInvocationError):
        ProviderRouter({"nvidia": _FakeProvider("nvidia")}, primary="missing")  # type: ignore[arg-type]


def test_get_unknown_provider() -> None:
    router = ProviderRouter(
        {"nvidia": _FakeProvider("nvidia")},  # type: ignore[arg-type]
        primary="nvidia",
    )
    with pytest.raises(ProviderUnavailableError):
        router.get("nope")


@pytest.mark.asyncio
async def test_router_model_property_and_list() -> None:
    router = ProviderRouter(
        {
            "nvidia": _FakeProvider("nvidia"),
            "routesme": _FakeProvider("routesme"),
        },  # type: ignore[arg-type]
        primary="nvidia",
        backup="routesme",
    )
    assert router.model == "nvidia-model"
    assert router.list_providers() == ["nvidia", "routesme"]
    await router.start()
    await router.stop()
