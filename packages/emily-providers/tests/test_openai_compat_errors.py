"""In-depth OpenAI-compatible client error and retry tests."""

from __future__ import annotations

import json

import httpx
import pytest

from emily.core.types.provider import ProviderStatus
from emily.providers.errors import ProviderInvocationError, ProviderUnavailableError
from emily.providers.openai_compat import OpenAICompatibleClient


def _client_with_transport(handler: object) -> OpenAICompatibleClient:
    client = OpenAICompatibleClient(
        name="mock",
        base_url="https://example.test/v1",
        api_key="test-key",
        model="mock-model",
        timeout_seconds=5.0,
        max_retries=1,
    )
    client._client = httpx.AsyncClient(
        base_url="https://example.test/v1",
        headers={"Authorization": "Bearer test-key"},
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )
    return client


@pytest.mark.asyncio
async def test_chat_http_400_raises_invocation_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad request"})

    client = _client_with_transport(handler)
    try:
        with pytest.raises(ProviderInvocationError) as exc:
            await client.chat([{"role": "user", "content": "hi"}])
        assert "400" in exc.value.message
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_chat_http_429_raises_invocation_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    client = _client_with_transport(handler)
    try:
        with pytest.raises(ProviderInvocationError) as exc:
            await client.chat([{"role": "user", "content": "hi"}])
        assert "429" in exc.value.message
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_chat_http_500_retries_then_unavailable() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="unavailable")

    client = _client_with_transport(handler)
    try:
        with pytest.raises(ProviderUnavailableError):
            await client.chat([{"role": "user", "content": "hi"}])
        assert calls["n"] == 2  # initial + 1 retry (max_retries=1)
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_chat_empty_choices() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"model": "mock-model", "choices": [], "usage": {}},
        )

    client = _client_with_transport(handler)
    try:
        with pytest.raises(ProviderInvocationError, match="no choices"):
            await client.chat([{"role": "user", "content": "hi"}])
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_chat_fills_total_tokens_when_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "mock-model",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 6},
            },
        )

    client = _client_with_transport(handler)
    try:
        result = await client.chat([{"role": "user", "content": "hi"}])
        assert result.usage.total_tokens == 10
        assert result.estimated_cost_usd >= 0
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_unstarted_client_raises() -> None:
    client = OpenAICompatibleClient(
        name="mock",
        base_url="https://example.test/v1",
        api_key="x",
        model="m",
    )
    with pytest.raises(ProviderUnavailableError, match="not started"):
        await client.chat([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_health_empty_api_key_unavailable() -> None:
    client = OpenAICompatibleClient(
        name="mock",
        base_url="https://example.test/v1",
        api_key="",
        model="m",
    )
    await client.start()
    try:
        assert await client.probe_health() == ProviderStatus.UNAVAILABLE
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_health_401_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    client = _client_with_transport(handler)
    try:
        assert await client.probe_health() == ProviderStatus.UNAVAILABLE
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_health_500_degraded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = _client_with_transport(handler)
    try:
        assert await client.probe_health() == ProviderStatus.DEGRADED
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_stream_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad stream")

    client = _client_with_transport(handler)
    try:
        with pytest.raises(ProviderInvocationError):
            async for _ in client.stream_chat([{"role": "user", "content": "hi"}]):
                pass
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_start_is_idempotent() -> None:
    client = OpenAICompatibleClient(
        name="mock",
        base_url="https://example.test/v1",
        api_key="x",
        model="m",
    )
    await client.start()
    first = client._client
    await client.start()
    assert client._client is first
    await client.stop()
    assert client._client is None


@pytest.mark.asyncio
async def test_chat_passes_max_tokens_and_extra() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        seen.update(body)
        return httpx.Response(
            200,
            json={
                "model": "mock-model",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    client = _client_with_transport(handler)
    try:
        await client.chat(
            [{"role": "user", "content": "hi"}],
            max_tokens=16,
            extra={"top_p": 0.9},
        )
        assert seen["max_tokens"] == 16
        assert seen["top_p"] == 0.9
        assert seen["stream"] is False
    finally:
        await client.stop()
