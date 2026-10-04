"""Provider domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from emily.core.types.provider import ProviderStatus


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None


class CompletionUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletion(BaseModel):
    """Normalized completion result across providers."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    content: str
    finish_reason: str | None = None
    usage: CompletionUsage = Field(default_factory=CompletionUsage)
    latency_ms: float = 0.0
    estimated_cost_usd: float = 0.0
    raw: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProviderHealthReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    model: str
    status: ProviderStatus
    latency_ms: float | None = None
    message: str = ""
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProviderCallMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    success: bool = True
    error: str | None = None
