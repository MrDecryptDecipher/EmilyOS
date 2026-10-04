"""Unit tests for extended OTLP, Execution Replay, and Analytics in Observability Suite."""

from datetime import UTC, datetime
import pytest

from emily.observability.analytics import ObservabilityAnalyticsEngine
from emily.observability.otlp import OTLPSpan, OTLPTraceExporter
from emily.observability.replay import ExecutionReplayEngine


def test_otlp_span_exporter():
    exporter = OTLPTraceExporter()
    span = OTLPSpan(
        span_id="span_1",
        trace_id="trace_1",
        name="mission_execution",
        start_time=datetime.now(UTC),
    )
    ok = exporter.export(span)
    assert ok is True
    assert len(exporter.list_exported()) == 1
    assert exporter.list_exported()[0].status_code == "OK"


def test_execution_replay_engine(tmp_path):
    engine = ExecutionReplayEngine(replay_dir=tmp_path)
    frame = engine.record_step(
        mission_id="m_100",
        step_name="step_1",
        input_data={"param": "value"},
        output_data={"result": "success"},
    )
    assert frame.mission_id == "m_100"

    replayed = engine.load_replay("m_100")
    assert len(replayed) == 1
    assert replayed[0].step_name == "step_1"
    assert replayed[0].input_data == {"param": "value"}


def test_observability_analytics_engine():
    analytics = ObservabilityAnalyticsEngine()
    analytics.record_llm_invocation("nvidia", tokens=500, latency_ms=120.0, cost_usd=0.001)
    analytics.record_llm_invocation("nvidia", tokens=300, latency_ms=80.0, cost_usd=0.0006)

    summary = analytics.summary()
    assert "nvidia" in summary
    assert summary["nvidia"]["total_requests"] == 2
    assert summary["nvidia"]["total_tokens"] == 800
    assert summary["nvidia"]["avg_latency_ms"] == 100.0
