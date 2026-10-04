"""Cost and latency analytics engine for LLMs and tools."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnalyticsMetrics:
    total_requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.total_requests if self.total_requests > 0 else 0.0


class ObservabilityAnalyticsEngine:
    """Aggregates performance, cost, and latency analytics across providers and tools."""

    def __init__(self) -> None:
        self._provider_metrics: dict[str, AnalyticsMetrics] = {}

    def record_llm_invocation(self, provider_name: str, tokens: int, latency_ms: float, cost_usd: float) -> None:
        """Record an LLM call metric."""
        if provider_name not in self._provider_metrics:
            self._provider_metrics[provider_name] = AnalyticsMetrics()
        m = self._provider_metrics[provider_name]
        m.total_requests += 1
        m.total_tokens += tokens
        m.total_cost_usd += cost_usd
        m.total_latency_ms += latency_ms

    def summary(self) -> dict[str, Any]:
        """Generate analytics summary report."""
        res: dict[str, Any] = {}
        for name, m in self._provider_metrics.items():
            res[name] = {
                "total_requests": m.total_requests,
                "total_tokens": m.total_tokens,
                "total_cost_usd": round(m.total_cost_usd, 6),
                "avg_latency_ms": round(m.avg_latency_ms, 2),
            }
        return res
