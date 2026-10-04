"""Metrics adapters with durable JSONL export."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class InMemoryMetrics:
    counters: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    gauges: dict[str, float] = field(default_factory=dict)
    histograms: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    export_path: Path | None = field(default=None)

    def __post_init__(self) -> None:
        if self.export_path is None:
            self.export_path = Path("data/metrics/metrics.jsonl")
        self.export_path.parent.mkdir(parents=True, exist_ok=True)

    def counter(
        self, name: str, value: float = 1.0, *, tags: Mapping[str, str] | None = None
    ) -> None:
        key = self._key(name, tags)
        self.counters[key] += value
        self._export("counter", key, self.counters[key])

    def gauge(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        key = self._key(name, tags)
        self.gauges[key] = value
        self._export("gauge", key, value)

    def histogram(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        key = self._key(name, tags)
        self.histograms[key].append(value)
        self._export("histogram", key, value)

    def snapshot(self) -> dict[str, object]:
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {k: list(v) for k, v in self.histograms.items()},
        }

    def _export(self, kind: str, key: str, value: float) -> None:
        if self.export_path is None:
            return
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "kind": kind,
            "key": key,
            "value": value,
        }
        with self.export_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

    @staticmethod
    def _key(name: str, tags: Mapping[str, str] | None) -> str:
        if not tags:
            return name
        suffix = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}|{suffix}"
