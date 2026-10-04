"""Adapter, analytics, and pricing depth tests."""

from __future__ import annotations

import json

import httpx
import pytest

from emily.providers.adapter import OpenAICompatibleProvider
from emily.providers.analytics import ProviderAnalytics
from emily.providers.models import ProviderCallMetrics
from emily.providers.openai_compat import OpenAICompatibleClient
from emily.providers.pricing import estimate_cost_usd


def _ok_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/models"):
        return httpx.Response(200, json={"data": []})
    body = json.loads(request.content.decode("utf-8"))
    if body.get("stream"):
        payload = 'data: {"choices":[{"delta":{"content":"X"}}]}\n\n' "data: [DONE]\n\n"
        return httpx.Response(200, content=payload.encode("utf-8"))
    return httpx.Response(
        200,
        json={
            "model": body["model"],
            "choices": [{"message": {"content": "adapter-ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )


@pytest.mark.asyncio
async def test_adapter_complete_and_stream_and_health_report() -> None:
    raw = OpenAICompatibleClient(
        name="nvidia",
        base_url="https://example.test/v1",
        api_key="k",
        model="z-ai/glm-5.2",
    )
    raw._client = httpx.AsyncClient(
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(_ok_handler),
    )
    provider = OpenAICompatibleProvider(raw)
    try:
        assert await provider.complete([{"role": "user", "content": "hi"}]) == "adapter-ok"
        chunks = [c async for c in provider.stream([{"role": "user", "content": "hi"}])]
        assert chunks == ["X"]
        report = await provider.health_report()
        assert report.name == "nvidia"
        assert report.status.value == "healthy"
        assert report.latency_ms is not None
    finally:
        await provider.stop()


def test_analytics_summary_empty_and_mixed() -> None:
    analytics = ProviderAnalytics()
    empty = analytics.summary()
    assert empty["calls"] == 0
    assert empty["avg_latency_ms"] == 0.0

    analytics.record(
        ProviderCallMetrics(
            provider="nvidia",
            model="m",
            latency_ms=10.0,
            total_tokens=5,
            estimated_cost_usd=0.01,
            success=True,
        )
    )
    analytics.record(
        ProviderCallMetrics(
            provider="routesme",
            model="m2",
            latency_ms=30.0,
            success=False,
            error="boom",
        )
    )
    summary = analytics.summary()
    assert summary["calls"] == 2
    assert summary["successes"] == 1
    assert summary["failures"] == 1
    assert summary["avg_latency_ms"] == 20.0
    assert summary["total_cost_usd"] == 0.01


def test_pricing_unknown_model_uses_fallback_card() -> None:
    cost = estimate_cost_usd(
        "unknown/model",
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
    )
    assert cost == 4.0
