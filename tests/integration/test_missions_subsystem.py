"""Missions subsystem integration with kernel."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from emily.agents.subsystem import AgentsSubsystem
from emily.config.settings import EmilySettings
from emily.core.types.mission import MissionStatus
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.missions.models import MissionSpec
from emily.missions.planner import HeuristicPlanner
from emily.missions.subsystem import MissionsSubsystem
from emily.providers.subsystem import ProvidersSubsystem


@pytest.mark.asyncio
async def test_missions_subsystem_run(tmp_path: Path) -> None:
    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        mission_llm_planner=False,
        nvidia_api_key=SecretStr(""),
        routesme_api_key=SecretStr(""),
        _env_file=None,
    )
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ProvidersSubsystem())
    kernel.register(MissionsSubsystem(missions_dir=tmp_path / "missions"))
    kernel.register(AgentsSubsystem())
    ctx = await kernel.start()
    try:
        assert ctx.mission_runtime is not None
        created = await ctx.mission_runtime.create(MissionSpec(goal="Build. Test. Ship."))
        finished = await ctx.mission_runtime.start(created.mission_id)
        assert finished.status == MissionStatus.SUCCEEDED
        listed = await ctx.mission_runtime.list()
        assert any(m.mission_id == finished.mission_id for m in listed)
    finally:
        await kernel.stop()
        assert ctx.mission_runtime is None
