"""Shared mission test helpers."""

from __future__ import annotations

from typing import Any

from emily.missions.models import TaskStatus
from emily.missions.runtime import MissionRuntime


class RecordingTaskExecutor:
    """Executes mission tasks for unit/integration tests."""

    async def execute_task(self, *, mission_id: str, task: dict[str, Any]) -> dict[str, Any]:
        out = dict(task)
        out["status"] = TaskStatus.SUCCEEDED.value
        out["result"] = f"executed:{mission_id}:{out.get('title')}"
        out["error"] = None
        return out


def attach_recording_executor(runtime: MissionRuntime) -> RecordingTaskExecutor:
    executor = RecordingTaskExecutor()
    runtime.set_task_executor(executor)
    return executor
