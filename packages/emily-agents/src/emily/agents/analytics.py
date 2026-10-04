"""In-process agent analytics accumulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from emily.agents.models import AgentRunResult
from emily.core.types.agent import AgentKind


@dataclass
class AgentAnalytics:
    runs: list[AgentRunResult] = field(default_factory=list)

    def record(self, result: AgentRunResult) -> None:
        self.runs.append(result)

    def summary(self) -> dict[str, Any]:
        if not self.runs:
            return {
                "runs": 0,
                "successes": 0,
                "failures": 0,
                "avg_attempts": 0.0,
                "avg_latency_ms": 0.0,
                "by_kind": {},
            }
        successes = sum(1 for r in self.runs if r.success)
        failures = len(self.runs) - successes
        by_kind: dict[str, int] = {}
        for run in self.runs:
            key = run.kind.value
            by_kind[key] = by_kind.get(key, 0) + 1
        return {
            "runs": len(self.runs),
            "successes": successes,
            "failures": failures,
            "avg_attempts": round(sum(r.attempts for r in self.runs) / len(self.runs), 3),
            "avg_latency_ms": round(sum(r.latency_ms for r in self.runs) / len(self.runs), 3),
            "by_kind": by_kind,
        }

    def by_kind_success_rate(self, kind: AgentKind) -> float:
        subset = [r for r in self.runs if r.kind == kind]
        if not subset:
            return 0.0
        return round(sum(1 for r in subset if r.success) / len(subset), 3)
