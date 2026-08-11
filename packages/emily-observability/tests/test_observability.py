"""Observability adapter tests."""

from __future__ import annotations

import io

import pytest

from emily.observability.logging import StructuredLogger
from emily.observability.metrics import InMemoryMetrics
from emily.observability.tracing import NoOpTracer


def test_structured_logger_emits_json_line() -> None:
    stream = io.StringIO()
    logger = StructuredLogger(level=10, stream=stream).bind(service="test")
    logger.info("hello", answer=42)
    line = stream.getvalue().strip()
    assert '"message":"hello"' in line or '"message": "hello"' in line
    assert "answer" in line


def test_metrics_counter_and_gauge() -> None:
    metrics = InMemoryMetrics()
    metrics.counter("requests", tags={"route": "a"})
    metrics.counter("requests", value=2, tags={"route": "a"})
    metrics.gauge("queue", 5)
    metrics.histogram("latency", 1.2)
    assert metrics.counters["requests|route=a"] == 3.0
    assert metrics.gauges["queue"] == 5.0
    assert metrics.histograms["latency"] == [1.2]


@pytest.mark.asyncio
async def test_noop_tracer_span() -> None:
    tracer = NoOpTracer()
    async with tracer.start_span("work", attributes={"k": "v"}) as span:
        assert span.name == "work"
        assert span.attributes["k"] == "v"
