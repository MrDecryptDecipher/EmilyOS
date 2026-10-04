"""Agent task executor + mission integration tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from emily.agents.executor import AgentTaskExecutor
from emily.agents.factory import WorkerFactory
from emily.agents.supervisor import AgentSupervisor
from emily.core.types.mission import MissionStatus
from emily.missions.models import MissionSpec, TaskStatus
from emily.missions.planner import HeuristicPlanner
from emily.missions.runtime import MissionRuntime
from emily.missions.store import MissionStore


class _ScriptedRouter:
    async def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        return f"completed: {messages[-1]['content'][:200]}"


def _supervisor(**kwargs: Any) -> AgentSupervisor:
    return AgentSupervisor(
        worker_factory=WorkerFactory(use_llm=True, router=_ScriptedRouter()),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_agent_executor_updates_task() -> None:
    executor = AgentTaskExecutor(_supervisor())
    updated = await executor.execute_task(
        mission_id="mis_1",
        task={
            "task_id": "tsk_1",
            "title": "Draft outline",
            "description": "Write outline",
            "status": TaskStatus.READY.value,
            "depends_on": [],
            "metadata": {},
        },
    )
    assert updated["status"] == TaskStatus.SUCCEEDED.value
    assert updated["result"]
    assert updated["metadata"]["agent_id"]
    assert updated["metadata"]["verification"]


@pytest.mark.asyncio
async def test_mission_uses_agent_executor(tmp_path: Path) -> None:
    runtime = MissionRuntime(MissionStore(tmp_path), planner=HeuristicPlanner())
    runtime.set_task_executor(AgentTaskExecutor(_supervisor()))
    created = await runtime.create(MissionSpec(goal="Research topic. Draft summary."))
    finished = await runtime.start(created.mission_id)
    assert finished.status == MissionStatus.SUCCEEDED
    for task in finished.all_tasks():
        assert task.status == TaskStatus.SUCCEEDED
        assert task.metadata.get("agent_id")
        assert task.result
        assert task.metadata.get("verification_verdict") == "ACCEPT"
