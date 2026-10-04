"""Mission domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from emily.core.ids import new_id, new_mission_id
from emily.core.types.mission import MissionPriority, MissionStatus


class TaskStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ControlSignal(StrEnum):
    RUN = "run"
    PAUSE = "pause"
    CANCEL = "cancel"


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(default_factory=lambda: new_id("tsk"))
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    depends_on: list[str] = Field(default_factory=list)
    result: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Objective(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective_id: str = Field(default_factory=lambda: new_id("obj"))
    title: str
    description: str = ""
    tasks: list[Task] = Field(default_factory=list)


class MissionSpec(BaseModel):
    """Input for creating a mission."""

    model_config = ConfigDict(extra="forbid")

    goal: str
    priority: MissionPriority = MissionPriority.NORMAL
    require_human_approval: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Mission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: str = Field(default_factory=new_mission_id)
    goal: str
    status: MissionStatus = MissionStatus.DRAFT
    priority: MissionPriority = MissionPriority.NORMAL
    objectives: list[Objective] = Field(default_factory=list)
    control: ControlSignal = ControlSignal.RUN
    require_human_approval: bool = False
    checkpoint_id: str | None = None
    reflection: str | None = None
    verification: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def all_tasks(self) -> list[Task]:
        tasks: list[Task] = []
        for objective in self.objectives:
            tasks.extend(objective.tasks)
        return tasks

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)
