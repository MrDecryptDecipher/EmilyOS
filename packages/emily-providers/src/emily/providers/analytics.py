"""In-process provider analytics accumulator."""

from __future__ import annotations

from dataclasses import dataclass, field

from emily.providers.models import ProviderCallMetrics


@dataclass
class ProviderAnalytics:
    calls: list[ProviderCallMetrics] = field(default_factory=list)

    def record(self, metrics: ProviderCallMetrics) -> None:
        self.calls.append(metrics)

    def summary(self) -> dict[str, float | int]:
        if not self.calls:
            return {
                "calls": 0,
                "successes": 0,
                "failures": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "avg_latency_ms": 0.0,
            }
        successes = sum(1 for c in self.calls if c.success)
        failures = len(self.calls) - successes
        total_tokens = sum(c.total_tokens for c in self.calls)
        total_cost = sum(c.estimated_cost_usd for c in self.calls)
        avg_latency = sum(c.latency_ms for c in self.calls) / len(self.calls)
        return {
            "calls": len(self.calls),
            "successes": successes,
            "failures": failures,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 8),
            "avg_latency_ms": round(avg_latency, 3),
        }
