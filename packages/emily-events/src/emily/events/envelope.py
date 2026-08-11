"""Immutable event envelope."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from emily.core.ids import new_correlation_id, new_event_id


class EventEnvelope(BaseModel):
    """Wire-level event structure for the in-process bus (and future transports)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(default_factory=new_event_id)
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = "unknown"
    correlation_id: str = Field(default_factory=new_correlation_id)
    causation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, str] = Field(default_factory=dict)
