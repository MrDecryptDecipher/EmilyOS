"""In-depth runtime state-machine and planner tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from emily.core.types.mission import MissionPriority, MissionStatus
from emily.events.bus import InProcessEventBus
from emily.missions.errors import MissionError, MissionStateError
from emily.missions.models import Mission, MissionSpec
from emily.missions.planner import HeuristicPlanner, LLMPlanner
from emily.missions.runtime import MissionRuntime
from emily.missions.store import MissionStore

from helpers import attach_recording_executor


class _FakeRouter:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.calls = 0

    async def achat(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert messages

        class _Result:
            def __init__(self, text: str) -> None:
                self.content = text

        return _Result(self.content or "")


@pytest.mark.asyncio
async def test_start_cancelled_and_succeeded_rejected(tmp_path: Path) -> None:
    runtime = MissionRuntime(MissionStore(tmp_path))
    attach_recording_executor(runtime)
    created = await runtime.create(MissionSpec(goal="X"))
    await runtime.cancel(created.mission_id)
    with pytest.raises(MissionStateError):
        await runtime.start(created.mission_id)

    ok = await runtime.create(MissionSpec(goal="A. B."))
    finished = await runtime.start(ok.mission_id)
    assert finished.status == MissionStatus.SUCCEEDED
    with pytest.raises(MissionStateError):
        await runtime.start(ok.mission_id)


@pytest.mark.asyncio
async def test_resume_invalid_status(tmp_path: Path) -> None:
    runtime = MissionRuntime(MissionStore(tmp_path))
    attach_recording_executor(runtime)
    created = await runtime.create(MissionSpec(goal="Only one"))
    finished = await runtime.start(created.mission_id)
    assert finished.status == MissionStatus.SUCCEEDED
    with pytest.raises(MissionStateError):
        await runtime.resume(finished.mission_id)


@pytest.mark.asyncio
async def test_events_emitted_on_lifecycle(tmp_path: Path) -> None:
    bus = InProcessEventBus()
    await bus.start()
    seen: list[str] = []

    async def capture(event_type: str, _payload: dict[str, object]) -> None:
        seen.append(event_type)

    bus.subscribe("mission.*", capture)
    runtime = MissionRuntime(MissionStore(tmp_path), event_bus=bus)
    attach_recording_executor(runtime)
    created = await runtime.create(MissionSpec(goal="Alpha. Beta."))
    await runtime.start(created.mission_id)
    await bus.stop()
    assert "mission.created" in seen
    assert "mission.started" in seen
    assert "mission.updated" in seen


@pytest.mark.asyncio
async def test_heuristic_empty_goal() -> None:
    mission = Mission(goal="   ")
    planned = await HeuristicPlanner().plan(mission)
    assert len(planned.all_tasks()) == 1
    assert "Complete requested work" in planned.all_tasks()[0].description


@pytest.mark.asyncio
async def test_llm_planner_success_and_fail_closed() -> None:
    ok_router = _FakeRouter(content="Gather requirements\nImplement feature\nWrite tests")
    planner = LLMPlanner(router=ok_router)
    planned = await planner.plan(Mission(goal="Ship feature"))
    assert len(planned.all_tasks()) == 3
    assert ok_router.calls == 1

    bad_router = _FakeRouter(error=RuntimeError("provider down"))
    with pytest.raises(MissionError):
        await LLMPlanner(router=bad_router).plan(Mission(goal="One. Two."))

    empty_router = _FakeRouter(content="\n\n")
    with pytest.raises(MissionError):
        await LLMPlanner(router=empty_router).plan(Mission(goal="Fallback. Path."))


@pytest.mark.asyncio
async def test_create_default_flags(tmp_path: Path) -> None:
    heuristic = MissionRuntime.create_default(
        missions_dir=tmp_path / "h",
        provider_router=_FakeRouter(content="x"),
        use_llm_planner=False,
    )
    assert isinstance(heuristic.planner, HeuristicPlanner)

    llm = MissionRuntime.create_default(
        missions_dir=tmp_path / "l",
        provider_router=_FakeRouter(content="Task one\nTask two\nTask three"),
        use_llm_planner=True,
    )
    assert isinstance(llm.planner, LLMPlanner)


@pytest.mark.asyncio
async def test_priority_and_metadata_roundtrip(tmp_path: Path) -> None:
    runtime = MissionRuntime(MissionStore(tmp_path))
    attach_recording_executor(runtime)
    created = await runtime.create(
        MissionSpec(
            goal="Critical path. Verify.",
            priority=MissionPriority.CRITICAL,
            require_human_approval=True,
            metadata={"source": "test"},
        )
    )
    assert created.priority == MissionPriority.CRITICAL
    assert created.require_human_approval is True
    assert created.metadata["source"] == "test"
    finished = await runtime.start(created.mission_id)
    reloaded = await runtime.get(finished.mission_id)
    assert reloaded.priority == MissionPriority.CRITICAL
    assert reloaded.metadata["source"] == "test"
    assert "events" in reloaded.metadata


@pytest.mark.asyncio
async def test_concurrent_missions(tmp_path: Path) -> None:
    import asyncio

    runtime = MissionRuntime(MissionStore(tmp_path))
    attach_recording_executor(runtime)

    async def run_one(goal: str) -> MissionStatus:
        created = await runtime.create(MissionSpec(goal=goal))
        finished = await runtime.start(created.mission_id)
        return finished.status

    statuses = await asyncio.gather(
        run_one("A1. A2."),
        run_one("B1. B2. B3."),
        run_one("C1."),
    )
    assert statuses == [
        MissionStatus.SUCCEEDED,
        MissionStatus.SUCCEEDED,
        MissionStatus.SUCCEEDED,
    ]
    listed = await runtime.list()
    assert len(listed) == 3
