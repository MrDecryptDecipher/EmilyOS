"""In-depth mission graph path tests."""

from __future__ import annotations

from typing import Any

import pytest

from emily.core.types.mission import MissionStatus
from emily.missions.control import ControlPlane
from emily.missions.executor_port import TaskExecutorSlot
from emily.missions.graph import MissionGraphFactory
from emily.missions.models import ControlSignal, TaskStatus
from emily.missions.planner import HeuristicPlanner


class _RecordingExecutor:
    async def execute_task(self, *, mission_id: str, task: dict[str, Any]) -> dict[str, Any]:
        out = dict(task)
        if out.get("title") == "boom":
            out["status"] = TaskStatus.FAILED.value
            out["error"] = "forced failure"
            return out
        out["status"] = TaskStatus.SUCCEEDED.value
        out["result"] = f"executed:{mission_id}:{out.get('title')}"
        return out


def _factory(**kwargs: object) -> MissionGraphFactory:
    slot = TaskExecutorSlot()
    slot.executor = _RecordingExecutor()  # type: ignore[assignment]
    return MissionGraphFactory(
        planner=HeuristicPlanner(),
        executor_slot=slot,
        checkpoint_path=":memory:",
        **kwargs,  # type: ignore[arg-type]
    )


def _base_state(mission_id: str, **extra: object) -> dict[str, object]:
    state: dict[str, object] = {
        "mission_id": mission_id,
        "goal": "A. B. C.",
        "status": MissionStatus.DRAFT.value,
        "control": ControlSignal.RUN.value,
        "entry": "plan",
        "objectives": [],
        "current_task_index": 0,
        "events": [],
        "extras": {},
    }
    state.update(extra)
    return state


@pytest.mark.asyncio
async def test_graph_full_happy_path_emits_events() -> None:
    factory = _factory()
    graph = factory.compile()
    result = await graph.ainvoke(
        _base_state("mis_happy"),
        config={"configurable": {"thread_id": "mis_happy"}},
    )
    assert result["status"] == MissionStatus.SUCCEEDED.value
    events = result.get("events", [])
    assert "plan:completed" in events
    assert "verify:passed" in events
    assert "reflect:completed" in events
    assert "finalize:succeeded" in events


@pytest.mark.asyncio
async def test_graph_fails_without_executor() -> None:
    factory = MissionGraphFactory(
        planner=HeuristicPlanner(),
        checkpoint_path=":memory:",
    )
    graph = factory.compile()
    result = await graph.ainvoke(
        _base_state("mis_no_exec"),
        config={"configurable": {"thread_id": "mis_no_exec"}},
    )
    assert result["status"] == MissionStatus.FAILED.value
    assert "no task executor" in str(result.get("error", ""))


@pytest.mark.asyncio
async def test_graph_pause_at_execute_boundary() -> None:
    control = ControlPlane()
    factory = _factory(control_plane=control)
    graph = factory.compile()
    planned = await graph.ainvoke(
        _base_state("mis_pause_plan"),
        config={"configurable": {"thread_id": "mis_pause_plan"}},
    )
    assert planned["status"] == MissionStatus.SUCCEEDED.value

    control.set("mis_pause_exec", ControlSignal.PAUSE)
    objectives = planned["objectives"]
    result = await graph.ainvoke(
        _base_state(
            "mis_pause_exec",
            entry="execute",
            objectives=objectives,
            current_task_index=0,
            status=MissionStatus.RUNNING.value,
            control=ControlSignal.PAUSE.value,
        ),
        config={"configurable": {"thread_id": "mis_pause_exec"}},
    )
    assert result["status"] == MissionStatus.PAUSED.value
    assert "execute:paused" in result["events"]


@pytest.mark.asyncio
async def test_graph_verify_failed_path() -> None:
    factory = _factory()
    graph = factory.compile()
    objectives = [
        {
            "objective_id": "obj_1",
            "title": "Primary",
            "description": "x",
            "tasks": [
                {
                    "task_id": "tsk_1",
                    "title": "boom",
                    "description": "boom",
                    "status": TaskStatus.READY.value,
                    "depends_on": [],
                    "result": None,
                    "error": None,
                    "metadata": {},
                }
            ],
        }
    ]
    result = await graph.ainvoke(
        _base_state(
            "mis_verify_fail",
            entry="execute",
            objectives=objectives,
            current_task_index=0,
            status=MissionStatus.RUNNING.value,
        ),
        config={"configurable": {"thread_id": "mis_verify_fail"}},
    )
    assert result["status"] == MissionStatus.FAILED.value
