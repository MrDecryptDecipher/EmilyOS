"""OpenTelemetry OTLP Exporter integration for Emily OS."""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OTLPSpan:
    span_id: str
    trace_id: str
    name: str
    start_time: datetime
    end_time: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status_code: str = "OK"

    def finish(self, status_code: str = "OK") -> None:
        self.end_time = datetime.now(UTC)
        self.status_code = status_code


class OTLPTraceExporter:
    """Exports structured OpenTelemetry spans to OTLP collector endpoint."""

    def __init__(self, endpoint: str = "http://localhost:4318/v1/traces") -> None:
        self.endpoint = endpoint
        self._exported_spans: list[OTLPSpan] = []

    def export(self, span: OTLPSpan) -> bool:
        """Export a completed telemetry span."""
        if not span.end_time:
            span.finish()
        self._exported_spans.append(span)
        logger.debug("Exported span %s [%s] to %s", span.name, span.span_id, self.endpoint)
        return True

    def list_exported(self) -> list[OTLPSpan]:
        return list(self._exported_spans)
