"""Kernel integration for memory subsystem."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from emily.agents.models import AgentTaskRequest
from emily.agents.subsystem import AgentsSubsystem
from emily.config.settings import EmilySettings
from emily.core.types.memory import MemoryKind
from emily.core.types.mission import MissionStatus
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.memory.models import MemoryQuery
from emily.memory.subsystem import MemorySubsystem
from emily.missions.models import MissionSpec
from emily.missions.subsystem import MissionsSubsystem
from emily.providers.subsystem import ProvidersSubsystem


@pytest.mark.asyncio
async def test_memory_subsystem_with_mission_and_agent_events(tmp_path: Path) -> None:
    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        nvidia_api_key=SecretStr(""),
        routesme_api_key=SecretStr(""),
        mission_llm_planner=False,
        memory_enabled=True,
        memory_directory=tmp_path / "memory",
        world_directory=tmp_path / "world",
        agent_history_directory=tmp_path / "agents",
        _env_file=None,
    )
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
            "User prefers concise answers",
            kind=MemoryKind.PREFERENCES,
            title="Preference",
            importance=0.9,
        )
        created = await ctx.mission_runtime.create(  # type: ignore[union-attr]
            MissionSpec(goal="Research Contoso. Draft summary.")
        )
        finished = await ctx.mission_runtime.start(created.mission_id)  # type: ignore[union-attr]
        assert finished.status == MissionStatus.SUCCEEDED

        result = await ctx.agent_supervisor.run_task(  # type: ignore[union-attr]
            AgentTaskRequest(title="Research market for Contoso")
        )
        assert result.success is True

        hits = await ctx.memory_runtime.search(MemoryQuery(text="Contoso", limit=10))
        assert hits
        stats = await ctx.memory_runtime.stats()
        assert stats["memory_total"] >= 2
        assert stats["world_entities"] >= 1
        health = await kernel.health()
        memory_report = next(s for s in health["subsystems"] if s["name"] == "memory")
        assert memory_report["healthy"] is True
    finally:
        await kernel.stop()
        assert ctx.memory_runtime is None
