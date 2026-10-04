"""Mission runtime and graph tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from emily.core.types.mission import MissionStatus
from emily.missions.control import ControlPlane
from emily.missions.models import ControlSignal, Mission, MissionSpec, Objective, TaskStatus
from emily.missions.planner import HeuristicPlanner
from emily.missions.runtime import MissionRuntime
from emily.missions.store import MissionStore

from helpers import attach_recording_executor


@pytest.mark.asyncio
async def test_heuristic_plan_and_full_run(tmp_path: Path) -> None:
    runtime = MissionRuntime(MissionStore(tmp_path), planner=HeuristicPlanner())
    attach_recording_executor(runtime)
    created = await runtime.create(
        MissionSpec(goal="Research topic. Draft outline. Write summary.")
    )
    finished = await runtime.start(created.mission_id)
    assert finished.status == MissionStatus.SUCCEEDED
    assert finished.verification is not None
    assert finished.reflection is not None
    assert len(finished.all_tasks()) >= 3
    assert all(t.status == TaskStatus.SUCCEEDED for t in finished.all_tasks())


@pytest.mark.asyncio
async def test_cancel_api_and_graph_cancel_path(tmp_path: Path) -> None:
    store = MissionStore(tmp_path)
    control = ControlPlane()
    runtime = MissionRuntime(store, planner=HeuristicPlanner(), control_plane=control)
    attach_recording_executor(runtime)
    created = await runtime.create(MissionSpec(goal="Do work. More work."))
    cancelled = await runtime.cancel(created.mission_id)
    assert cancelled.status == MissionStatus.CANCELLED

    # Direct graph path: cancel signal honored at plan node.
    from emily.missions.graph import MissionGraphFactory

    factory = MissionGraphFactory(
        planner=HeuristicPlanner(),
        control_plane=control,
        checkpoint_path=":memory:",
    )
    graph = factory.compile()
    control.set("mis_cancel_graph", ControlSignal.CANCEL)
    result = await graph.ainvoke(
        {
            "mission_id": "mis_cancel_graph",
            "goal": "x",
            "status": MissionStatus.DRAFT.value,
            "control": ControlSignal.CANCEL.value,
            "entry": "plan",
            "objectives": [],
            "current_task_index": 0,
            "events": [],
            "extras": {},
        },
        config={"configurable": {"thread_id": "mis_cancel_graph"}},
    )
    assert result["status"] == MissionStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_pause_then_resume(tmp_path: Path) -> None:
    store = MissionStore(tmp_path)
    runtime = MissionRuntime(store, planner=HeuristicPlanner())
    attach_recording_executor(runtime)
    created = await runtime.create(MissionSpec(goal="One. Two. Three."))
    planned = await HeuristicPlanner().plan(
        Mission(mission_id=created.mission_id, goal=created.goal)
    )
    # Simulate paused mid-flight after first task.
    tasks = planned.all_tasks()
    tasks[0].status = TaskStatus.SUCCEEDED
    tasks[0].result = "done"
    if len(tasks) > 1:
        tasks[1].status = TaskStatus.READY
    planned.objectives = [Objective(title="Primary", description=created.goal, tasks=tasks)]
    planned.status = MissionStatus.PAUSED
    planned.metadata["current_task_index"] = 1
    await store.save(planned)

    resumed = await runtime.resume(planned.mission_id)
    assert resumed.status == MissionStatus.SUCCEEDED
    assert resumed.metadata["current_task_index"] >= 1


@pytest.mark.asyncio
async def test_pause_api_updates_store(tmp_path: Path) -> None:
    runtime = MissionRuntime(MissionStore(tmp_path))
    attach_recording_executor(runtime)
    created = await runtime.create(MissionSpec(goal="Hold"))
    paused = await runtime.pause(created.mission_id)
    assert paused.status == MissionStatus.PAUSED
    loaded = await runtime.get(created.mission_id)
    assert loaded.control == ControlSignal.PAUSE
