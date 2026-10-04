"""Milestone 2 in-depth smoke harness (offline-first, timed)."""

from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from emily.core.types.mission import MissionStatus
from emily.events.bus import InProcessEventBus
from emily.missions.control import ControlPlane
from emily.missions.errors import MissionStateError
from emily.missions.graph import MissionGraphFactory
from emily.missions.models import ControlSignal, MissionSpec
from emily.missions.planner import HeuristicPlanner
from emily.missions.runtime import MissionRuntime
from emily.missions.store import MissionStore


@dataclass
class ProbeResult:
    name: str
    ok: bool
    detail: str


async def probe_full_run(root: Path) -> ProbeResult:
    runtime = MissionRuntime(MissionStore(root / "full"))
    created = await runtime.create(MissionSpec(goal="Research. Draft. Ship."))
    finished = await runtime.start(created.mission_id)
    ok = finished.status == MissionStatus.SUCCEEDED and len(finished.all_tasks()) == 3
    return ProbeResult("mission:full_run", ok, f"status={finished.status.value}")


async def probe_pause_resume(root: Path) -> ProbeResult:
    from emily.missions.models import Mission, Objective, TaskStatus
    from emily.missions.planner import HeuristicPlanner

    store = MissionStore(root / "pause")
    runtime = MissionRuntime(store)
    created = await runtime.create(MissionSpec(goal="One. Two. Three. Four."))
    planned = await HeuristicPlanner().plan(
        Mission(mission_id=created.mission_id, goal=created.goal)
    )
    tasks = planned.all_tasks()
    tasks[0].status = TaskStatus.SUCCEEDED
    tasks[0].result = "done"
    tasks[1].status = TaskStatus.READY
    planned.objectives = [Objective(title="Primary", description=created.goal, tasks=tasks)]
    planned.status = MissionStatus.PAUSED
    planned.metadata["current_task_index"] = 1
    await store.save(planned)
    resumed = await runtime.resume(planned.mission_id)
    return ProbeResult(
        "mission:pause_resume",
        resumed.status == MissionStatus.SUCCEEDED,
        f"status={resumed.status.value} idx={resumed.metadata.get('current_task_index')}",
    )


async def probe_cancel_guards(root: Path) -> ProbeResult:
    runtime = MissionRuntime(MissionStore(root / "cancel"))
    created = await runtime.create(MissionSpec(goal="Cancel me"))
    await runtime.cancel(created.mission_id)
    try:
        await runtime.start(created.mission_id)
        return ProbeResult("mission:cancel_guard", False, "start should have failed")
    except MissionStateError as exc:
        return ProbeResult("mission:cancel_guard", True, exc.message)


async def probe_graph_pause_signal() -> ProbeResult:
    control = ControlPlane()
    factory = MissionGraphFactory(planner=HeuristicPlanner(), control_plane=control)
    graph = factory.compile()
    control.set("smoke_pause", ControlSignal.PAUSE)
    result = await graph.ainvoke(
        {
            "mission_id": "smoke_pause",
            "goal": "x",
            "status": MissionStatus.DRAFT.value,
            "control": ControlSignal.PAUSE.value,
            "entry": "plan",
            "objectives": [],
            "current_task_index": 0,
            "events": [],
            "extras": {},
        },
        config={"configurable": {"thread_id": "smoke_pause"}},
    )
    return ProbeResult(
        "graph:pause_at_plan",
        result["status"] == MissionStatus.PAUSED.value,
        f"status={result['status']}",
    )


async def probe_events(root: Path) -> ProbeResult:
    bus = InProcessEventBus()
    await bus.start()
    seen: list[str] = []

    async def capture(event_type: str, _payload: dict[str, object]) -> None:
        seen.append(event_type)

    bus.subscribe("mission.*", capture)
    runtime = MissionRuntime(MissionStore(root / "events"), event_bus=bus)
    created = await runtime.create(MissionSpec(goal="Emit. Events."))
    await runtime.start(created.mission_id)
    await bus.stop()
    required = {"mission.created", "mission.started", "mission.updated"}
    ok = required.issubset(set(seen))
    return ProbeResult("mission:events", ok, f"seen={seen}")


async def probe_concurrency(root: Path) -> ProbeResult:
    runtime = MissionRuntime(MissionStore(root / "conc"))

    async def one(goal: str) -> MissionStatus:
        created = await runtime.create(MissionSpec(goal=goal))
        finished = await runtime.start(created.mission_id)
        return finished.status

    statuses = await asyncio.gather(one("A. B."), one("C. D. E."), one("F."))
    ok = all(s == MissionStatus.SUCCEEDED for s in statuses)
    return ProbeResult("mission:concurrency", ok, f"statuses={[s.value for s in statuses]}")


async def main() -> int:
    with tempfile.TemporaryDirectory(prefix="emily-m2-smoke-") as tmp:
        root = Path(tmp)
        results = [
            await probe_full_run(root),
            await probe_pause_resume(root),
            await probe_cancel_guards(root),
            await probe_graph_pause_signal(),
            await probe_events(root),
            await probe_concurrency(root),
        ]
    payload: dict[str, Any] = {
        "results": [asdict(r) for r in results],
        "passed": sum(1 for r in results if r.ok),
        "failed": sum(1 for r in results if not r.ok),
        "total": len(results),
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
