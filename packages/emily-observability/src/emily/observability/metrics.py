"""In-memory metrics adapter for M0."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass
class InMemoryMetrics:
    counters: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    gauges: dict[str, float] = field(default_factory=dict)
    histograms: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def counter(
        self, name: str, value: float = 1.0, *, tags: Mapping[str, str] | None = None
    ) -> None:
        key = self._key(name, tags)
        self.counters[key] += value

    def gauge(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        self.gauges[self._key(name, tags)] = value

    def histogram(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        self.histograms[self._key(name, tags)].append(value)

    @staticmethod
    def _key(name: str, tags: Mapping[str, str] | None) -> str:
        if not tags:
            return name
        suffix = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}|{suffix}"
