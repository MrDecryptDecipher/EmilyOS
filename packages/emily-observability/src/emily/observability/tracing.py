"""File-backed JSONL tracer for durable span records."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class _Span:
    def __init__(
        self, name: str, attributes: Mapping[str, str | int | float | bool] | None
    ) -> None:
        self.name = name
        self.attributes = dict(attributes or {})
        self.span_id = uuid4().hex[:16]
        self.started_at = datetime.now(UTC)


class FileJSONLTracer:
    """Writes start/end span events to a JSONL file."""

    def __init__(self, path: Path | str = Path("data/traces/spans.jsonl")) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, payload: dict[str, object]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")

    @asynccontextmanager
    async def start_span(
        self,
        name: str,
        *,
        attributes: Mapping[str, str | int | float | bool] | None = None,
    ) -> AsyncIterator[_Span]:
        span = _Span(name, attributes)
        self._write(
            {
                "event": "span.start",
                "span_id": span.span_id,
                "name": span.name,
                "attributes": span.attributes,
                "ts": span.started_at.isoformat(),
            }
        )
        error: str | None = None
        try:
            yield span
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            self._write(
                {
                    "event": "span.end",
                    "span_id": span.span_id,
                    "name": span.name,
                    "error": error,
                    "ts": datetime.now(UTC).isoformat(),
                }
            )


# Backward-compatible alias — previously discarded all spans.
NoOpTracer = FileJSONLTracer
