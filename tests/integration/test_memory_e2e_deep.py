"""Deep e2e integration for Milestone 4 memory + world model."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import SecretStr

from emily.agents.models import AgentTaskRequest
from emily.agents.subsystem import AgentsSubsystem
from emily.config.settings import EmilySettings
from emily.core.types.memory import MemoryKind
from emily.core.types.mission import MissionStatus
from emily.events.bus import InProcessEventBus
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.memory.models import MemoryQuery, ObservedRelation, WorldObservation
from emily.memory.runtime import MemoryRuntime
from emily.memory.subsystem import MemorySubsystem
from emily.missions.models import MissionSpec
from emily.missions.subsystem import MissionsSubsystem
from emily.providers.subsystem import ProvidersSubsystem


def _settings(tmp_path: Path, **kwargs: object) -> EmilySettings:
    base: dict[str, object] = {
        "environment": "test",
        "log_level": "ERROR",
        "nvidia_api_key": SecretStr(""),
        "routesme_api_key": SecretStr(""),
        "mission_llm_planner": False,
        "memory_enabled": True,
        "memory_directory": tmp_path / "memory",
        "world_directory": tmp_path / "world",
        "agent_history_directory": tmp_path / "agents",
        "agent_history_enabled": True,
        "_env_file": None,
    }
    base.update(kwargs)
    return EmilySettings(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_full_stack_memory_mission_agent_world(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ProvidersSubsystem())
    kernel.register(MemorySubsystem())
    kernel.register(MissionsSubsystem(missions_dir=tmp_path / "missions"))
    kernel.register(AgentsSubsystem(history_dir=tmp_path / "agents"))
    ctx = await kernel.start()
    try:
        assert ctx.memory_runtime is not None
        await ctx.memory_runtime.remember(
            "Preference: keep answers concise for Contoso ops",
            kind=MemoryKind.PREFERENCES,
            title="Contoso preference",
            importance=0.95,
            tags=["contoso", "preference"],
        )
        await ctx.memory_runtime.observe(
            WorldObservation(
                text="Contoso depends on NVIDIA NIM",
                entities=["Contoso", "NVIDIA"],
                relations=[
                    ObservedRelation(subject="Contoso", predicate="depends_on", object="NVIDIA")
                ],
                source="seed",
            )
        )

        created = await ctx.mission_runtime.create(  # type: ignore[union-attr]
            MissionSpec(goal="Research Contoso. Draft summary. Verify findings.")
        )
        finished = await ctx.mission_runtime.start(created.mission_id)  # type: ignore[union-attr]
        assert finished.status == MissionStatus.SUCCEEDED

        agent_result = await ctx.agent_supervisor.run_task(  # type: ignore[union-attr]
            AgentTaskRequest(
                title="Research Contoso market",
                description="Investigate Contoso competitors",
            )
        )
        assert agent_result.success is True

        mission_hits = await ctx.memory_runtime.search(
            MemoryQuery(text="Contoso", kinds=[MemoryKind.MISSION_HISTORY], limit=10)
        )
        exec_hits = await ctx.memory_runtime.search(
            MemoryQuery(text="Agent", kinds=[MemoryKind.EXECUTION_HISTORY], limit=10)
        )
        pref_hits = await ctx.memory_runtime.search(
            MemoryQuery(text="concise Contoso", kinds=[MemoryKind.PREFERENCES], limit=5)
        )
        assert mission_hits
        assert exec_hits
        assert pref_hits
        assert ctx.memory_runtime.world.get_entity("Contoso") is not None
        assert ctx.memory_runtime.world.get_entity("NVIDIA") is not None

        await ctx.memory_runtime.remember(
            "temp working scratch for Contoso",
            kind=MemoryKind.WORKING,
            importance=0.9,
        )
        result = await ctx.memory_runtime.consolidate()
        assert result.promoted >= 1
        still_pref = await ctx.memory_runtime.search(
            MemoryQuery(text="concise", kinds=[MemoryKind.PREFERENCES], limit=5)
        )
        assert still_pref

        health = await kernel.health()
        memory_report = next(s for s in health["subsystems"] if s["name"] == "memory")
        assert memory_report["healthy"] is True
        assert memory_report["details"]["memory_total"] >= 3
        assert memory_report["details"]["world_entities"] >= 2
    finally:
        await kernel.stop()


@pytest.mark.asyncio
async def test_memory_disabled_health_and_no_runtime(tmp_path: Path) -> None:
    settings = _settings(tmp_path, memory_enabled=False)
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(MemorySubsystem())
    ctx = await kernel.start()
    try:
        assert ctx.memory_runtime is None
        health = await kernel.health()
        memory_report = next(s for s in health["subsystems"] if s["name"] == "memory")
        assert memory_report["healthy"] is True
        assert memory_report["message"] == "disabled"
    finally:
        await kernel.stop()


@pytest.mark.asyncio
async def test_concurrent_memory_ops_under_runtime(tmp_path: Path) -> None:
    bus = InProcessEventBus()
    await bus.start()
    runtime = MemoryRuntime(tmp_path / "m", tmp_path / "w", event_bus=bus)
    await runtime.start()

    async def write_and_search(i: int) -> int:
        await runtime.remember(
            f"Topic{i} retrieval concurrent payload",
            kind=MemoryKind.SEMANTIC,
            title=f"Topic{i}",
            importance=0.6,
        )
        hits = await runtime.search(MemoryQuery(text=f"Topic{i}", limit=3))
        return len(hits)

    counts = await asyncio.gather(*(write_and_search(i) for i in range(12)))
    assert all(c >= 1 for c in counts)
    stats = await runtime.stats()
    assert stats["memory_total"] >= 12
    await runtime.stop()
    await bus.stop()


@pytest.mark.asyncio
async def test_subsystem_type_guard() -> None:
    sub = MemorySubsystem()
    with pytest.raises(TypeError):
        await sub.on_start(object())
