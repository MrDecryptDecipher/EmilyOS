"""OpenAI-compatible client tests with mocked HTTP."""

from __future__ import annotations

import json

import httpx
import pytest

from emily.providers.openai_compat import OpenAICompatibleClient


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/models"):
        return httpx.Response(200, json={"data": [{"id": "mock-model"}]})
    if request.url.path.endswith("/chat/completions"):
        body = json.loads(request.content.decode("utf-8"))
        if body.get("stream"):
            lines = [
                'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n',
                'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n',
                "data: [DONE]\n\n",
            ]
            return httpx.Response(200, content="".join(lines).encode("utf-8"))
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "Hello from mock"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 3,
                    "total_tokens": 8,
                },
            },
        )
    return httpx.Response(404, json={"error": "not found"})


@pytest.mark.asyncio
async def test_chat_completion_parses_usage() -> None:
    transport = httpx.MockTransport(_handler)
    client = OpenAICompatibleClient(
        name="mock",
        base_url="https://example.test/v1",
        api_key="test-key",
        model="mock-model",
    )
    client._client = httpx.AsyncClient(
        base_url="https://example.test/v1",
        headers={"Authorization": "Bearer test-key"},
        transport=transport,
    )
    try:
        result = await client.chat([{"role": "user", "content": "hi"}])
        assert result.content == "Hello from mock"
        assert result.usage.total_tokens == 8
        assert result.provider == "mock"
        assert result.latency_ms >= 0
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_stream_chat_yields_chunks() -> None:
    transport = httpx.MockTransport(_handler)
    client = OpenAICompatibleClient(
        name="mock",
        base_url="https://example.test/v1",
        api_key="test-key",
        model="mock-model",
    )
    client._client = httpx.AsyncClient(
        base_url="https://example.test/v1",
        transport=transport,
    )
    try:
        chunks: list[str] = []
        async for piece in client.stream_chat([{"role": "user", "content": "hi"}]):
            chunks.append(piece)
        assert "".join(chunks) == "Hello"
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_health_probe_healthy() -> None:
    transport = httpx.MockTransport(_handler)
    client = OpenAICompatibleClient(
        name="mock",
        base_url="https://example.test/v1",
        api_key="test-key",
        model="mock-model",
    )
    client._client = httpx.AsyncClient(
        base_url="https://example.test/v1",
        transport=transport,
    )
    try:
        status = await client.probe_health()
        assert status.value == "healthy"
    finally:
        await client.stop()
