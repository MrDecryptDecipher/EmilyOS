"""Concrete LLM adapter implementing the core port."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from emily.core.types.provider import ProviderStatus
from emily.providers.models import ChatCompletion, ProviderHealthReport
from emily.providers.openai_compat import OpenAICompatibleClient


class OpenAICompatibleProvider:
    """Adapter wrapping :class:`OpenAICompatibleClient` as an LLM provider."""

    def __init__(self, client: OpenAICompatibleClient) -> None:
        self._client = client
        self._last_status = ProviderStatus.UNKNOWN

    @property
    def name(self) -> str:
        return self._client.name

    @property
    def model(self) -> str:
        return self._client.model

    async def start(self) -> None:
        await self._client.start()

    async def stop(self) -> None:
        await self._client.stop()

    async def achat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> ChatCompletion:
        return await self._client.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=extra,
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
        async for chunk in self._client.stream_chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=extra,
        ):
            yield chunk

    async def health(self) -> ProviderStatus:
        status = await self._client.probe_health()
        self._last_status = status
        return status

    async def health_report(self) -> ProviderHealthReport:
        started = time.perf_counter()
        status = await self.health()
        latency_ms = (time.perf_counter() - started) * 1000.0
        return ProviderHealthReport(
            name=self.name,
            model=self.model,
            status=status,
            latency_ms=latency_ms,
            message=status.value,
        )
