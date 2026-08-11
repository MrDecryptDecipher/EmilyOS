"""Cross-cutting enumerations and value objects."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SubsystemState(StrEnum):
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPED = "stopped"
    FAILED = "failed"


class HealthStatus(BaseModel):
    """Normalized health report for subsystems and providers."""

    model_config = ConfigDict(extra="forbid")

    name: str
    healthy: bool
    state: SubsystemState = SubsystemState.CREATED
    message: str = ""
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, str | int | float | bool] = Field(default_factory=dict)
