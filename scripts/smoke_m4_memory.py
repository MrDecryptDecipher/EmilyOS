"""Milestone 4 in-depth smoke harness (offline-first)."""

from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from emily.agents.models import AgentTaskRequest
from emily.agents.subsystem import AgentsSubsystem
from emily.config.settings import EmilySettings
from emily.core.types.memory import MemoryKind
from emily.core.types.mission import MissionStatus
from emily.events.bus import InProcessEventBus
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.memory.models import MemoryQuery, MemoryWrite, ObservedRelation, WorldObservation
from emily.memory.runtime import MemoryRuntime
from emily.memory.subsystem import MemorySubsystem
from emily.missions.models import MissionSpec
from emily.missions.runtime import MissionRuntime
from emily.missions.store import MissionStore
from emily.missions.subsystem import MissionsSubsystem
from emily.providers.subsystem import ProvidersSubsystem


@dataclass
class ProbeResult:
    name: str
    ok: bool
    detail: str


async def probe_crud_search(root: Path) -> ProbeResult:
    runtime = MemoryRuntime(root / "mem", root / "world")
    await runtime.start()
    await runtime.remember("vector retrieval roadmap", kind=MemoryKind.SEMANTIC, title="Roadmap")
    hits = await runtime.search(MemoryQuery(text="retrieval roadmap", limit=3))
    ok = bool(hits) and "roadmap" in hits[0].record.content.lower()
    await runtime.stop()
    return ProbeResult("memory:crud_search", ok, f"hits={len(hits)}")


async def probe_world(root: Path) -> ProbeResult:
    runtime = MemoryRuntime(root / "mem2", root / "world2")
    await runtime.start()
    snap = await runtime.observe(
        WorldObservation(
            text="Contoso depends on Azure",
            entities=["Contoso", "Azure"],
            relations=[ObservedRelation(subject="Contoso", predicate="depends_on", object="Azure")],
        )
    )
    ok = (
        int(snap.metadata["entity_count"]) >= 2
        and int(snap.metadata["relation_count"]) >= 1
        and runtime.world.get_entity("Contoso") is not None
    )
    await runtime.stop()
    return ProbeResult("memory:world_observe", ok, f"meta={snap.metadata}")


async def probe_consolidate(root: Path) -> ProbeResult:
    runtime = MemoryRuntime(root / "mem3", root / "world3")
    await runtime.start()
    await runtime.put(
        MemoryWrite(
            kind=MemoryKind.WORKING,
            content="Promote me please",
            importance=0.9,
            title="Keep",
        )
    )
    await runtime.put(
        MemoryWrite(
            kind=MemoryKind.TASK,
            content="Task episode for Contoso rollout",
            importance=0.8,
            title="Task",
        )
    )
    result = await runtime.consolidate()
    long_term = await runtime.store.list_kind(MemoryKind.LONG_TERM)
    episodic = await runtime.store.list_kind(MemoryKind.EPISODIC)
    ok = result.promoted >= 2 and len(long_term) > 0 and len(episodic) > 0
    await runtime.stop()
    return ProbeResult(
        "memory:consolidate",
        ok,
        f"promoted={result.promoted} long_term={len(long_term)} episodic={len(episodic)}",
    )


async def probe_events(root: Path) -> ProbeResult:
    bus = InProcessEventBus()
    await bus.start()
    seen: list[str] = []

    async def capture(event_type: str, _payload: dict[str, object]) -> None:
        seen.append(event_type)

    bus.subscribe("memory.*", capture)
    bus.subscribe("world.*", capture)
    runtime = MemoryRuntime(root / "mem4", root / "world4", event_bus=bus)
    await runtime.start()
    await runtime.remember("hello world model", kind=MemoryKind.WORKING)
    await runtime.search(MemoryQuery(text="hello"))
    await runtime.observe(WorldObservation(text="Fabrikam opened an office", entities=["Fabrikam"]))
    await runtime.consolidate()
    await runtime.stop()
    await bus.stop()
    required = {"memory.written", "memory.retrieved", "world.updated", "memory.consolidated"}
    ok = required.issubset(set(seen))
    return ProbeResult("memory:events", ok, f"seen={sorted(set(seen))}")


async def probe_persistence(root: Path) -> ProbeResult:
    mem = root / "persist-mem"
    world = root / "persist-world"
    runtime = MemoryRuntime(mem, world)
    await runtime.start()
    rec = await runtime.remember("durable semantic note", kind=MemoryKind.SEMANTIC, title="Durable")
    await runtime.observe(
        WorldObservation(
            text="EmilyOS runs on Windows",
            entities=["EmilyOS", "Windows"],
            relations=[
                ObservedRelation(subject="EmilyOS", predicate="runs_on", object="Windows")
            ],
        )
    )
    await runtime.stop()
    runtime2 = MemoryRuntime(mem, world)
    await runtime2.start()
    loaded = await runtime2.get(rec.memory_id)
    ok = "durable" in loaded.content.lower() and runtime2.world.get_entity("Windows") is not None
    await runtime2.stop()
    return ProbeResult("memory:persistence", ok, f"id={rec.memory_id}")


async def probe_concurrent(root: Path) -> ProbeResult:
    runtime = MemoryRuntime(root / "conc-mem", root / "conc-world")
    await runtime.start()

    async def one(i: int) -> bool:
        await runtime.remember(f"ConcurrentTopic{i} payload", kind=MemoryKind.SEMANTIC)
        hits = await runtime.search(MemoryQuery(text=f"ConcurrentTopic{i}", limit=2))
        return bool(hits)

    outcomes = await asyncio.gather(*(one(i) for i in range(10)))
    ok = all(outcomes)
    await runtime.stop()
    return ProbeResult("memory:concurrency", ok, f"ok={sum(outcomes)}/10")


async def probe_kernel_event_hooks(root: Path) -> ProbeResult:
    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        nvidia_api_key=SecretStr(""),
        routesme_api_key=SecretStr(""),
        mission_llm_planner=False,
        memory_enabled=True,
        memory_directory=root / "k-mem",
        world_directory=root / "k-world",
        agent_history_directory=root / "k-agents",
        _env_file=None,
    )
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ProvidersSubsystem())
    kernel.register(MemorySubsystem())
    kernel.register(MissionsSubsystem(missions_dir=root / "k-missions"))
    kernel.register(AgentsSubsystem(history_dir=root / "k-agents"))
    ctx = await kernel.start()
    try:
        assert ctx.memory_runtime is not None
        created = await ctx.mission_runtime.create(  # type: ignore[union-attr]
            MissionSpec(goal="Research Contoso. Draft summary.")
        )
        finished = await ctx.mission_runtime.start(created.mission_id)  # type: ignore[union-attr]
        agent = await ctx.agent_supervisor.run_task(  # type: ignore[union-attr]
            AgentTaskRequest(title="Research Contoso competitors")
        )
        mission_hits = await ctx.memory_runtime.search(
            MemoryQuery(text="Contoso", kinds=[MemoryKind.MISSION_HISTORY], limit=10)
        )
        exec_hits = await ctx.memory_runtime.search(
            MemoryQuery(text="research", kinds=[MemoryKind.EXECUTION_HISTORY], limit=10)
        )
        ok = (
            finished.status == MissionStatus.SUCCEEDED
            and agent.success
            and bool(mission_hits)
            and bool(exec_hits)
            and ctx.memory_runtime.world.get_entity("Contoso") is not None
        )
        return ProbeResult(
            "memory:kernel_hooks",
            ok,
            f"mission_hits={len(mission_hits)} exec_hits={len(exec_hits)}",
        )
    finally:
        await kernel.stop()


async def probe_mission_history_side_effect(root: Path) -> ProbeResult:
    runtime = MemoryRuntime(root / "mem5", root / "world5")
    await runtime.start()
    mission_rt = MissionRuntime(MissionStore(root / "missions"))
    created = await mission_rt.create(MissionSpec(goal="Research Alpha. Draft Beta."))
    finished = await mission_rt.start(created.mission_id)
    await runtime.remember(
        f"Mission finished {finished.status.value}: {finished.goal}",
        kind=MemoryKind.MISSION_HISTORY,
        title=finished.mission_id,
        importance=0.7,
        mission_id=finished.mission_id,
        source="smoke",
    )
    hits = await runtime.search(MemoryQuery(text="Alpha Beta", kinds=[MemoryKind.MISSION_HISTORY]))
    ok = finished.status == MissionStatus.SUCCEEDED and bool(hits)
    await runtime.stop()
    return ProbeResult("memory:mission_history", ok, f"hits={len(hits)}")


async def main() -> int:
    with tempfile.TemporaryDirectory(prefix="emily-m4-smoke-") as tmp:
        root = Path(tmp)
        results = [
            await probe_crud_search(root),
            await probe_world(root),
            await probe_consolidate(root),
            await probe_events(root),
            await probe_persistence(root),
            await probe_concurrent(root),
            await probe_kernel_event_hooks(root),
            await probe_mission_history_side_effect(root),
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
