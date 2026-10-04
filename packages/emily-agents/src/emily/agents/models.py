"""Agent runtime models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from emily.core.ids import new_agent_id
from emily.core.types.agent import AgentKind, AgentStatus


class VerificationVerdict(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


class AgentRoleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: AgentKind
    title: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    default_max_retries: int = 1
    output_style: str = "structured"


class AgentInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(default_factory=new_agent_id)
    kind: AgentKind
    status: AgentStatus = AgentStatus.SPAWNING
    mission_id: str | None = None
    task_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
    run_count: int = 0
    last_error: str | None = None

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)


class AgentTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str = ""
    mission_id: str | None = None
    task_id: str | None = None
    kind: AgentKind | None = None
    max_retries: int | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    prior_output: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VerificationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: VerificationVerdict
    reason: str
    score: float = 0.0
    criteria_met: list[str] = Field(default_factory=list)
    criteria_missed: list[str] = Field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.verdict == VerificationVerdict.ACCEPT

    def as_text(self) -> str:
        return f"{self.verdict.value}: {self.reason}"


class AgentRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    kind: AgentKind
    success: bool
    output: str
    verification: str | None = None
    decision: VerificationDecision | None = None
    attempts: int = 1
    latency_ms: float = 0.0
    error: str | None = None
    critique_trail: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRunRecord(BaseModel):
    """Persisted summary of a completed agent run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    agent_id: str
    kind: AgentKind
    title: str
    success: bool
    attempts: int
    latency_ms: float
    mission_id: str | None = None
    task_id: str | None = None
    verification: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    output_preview: str = ""


class PipelineStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str = ""
    kind: AgentKind | None = None
    handoff: bool = True


class PipelineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    steps: list[AgentRunResult] = Field(default_factory=list)
    final_output: str = ""
    error: str | None = None
