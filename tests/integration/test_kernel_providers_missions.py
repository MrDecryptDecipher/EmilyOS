"""Integration: providers + missions together under one kernel."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from emily.agents.subsystem import AgentsSubsystem
from emily.config.settings import EmilySettings
from emily.core.types.mission import MissionStatus
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.missions.models import MissionSpec
from emily.missions.subsystem import MissionsSubsystem
from emily.providers.subsystem import ProvidersSubsystem


@pytest.mark.asyncio
async def test_kernel_with_providers_and_missions(tmp_path: Path) -> None:
    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        nvidia_api_key=SecretStr(""),
        routesme_api_key=SecretStr(""),
        mission_llm_planner=False,
        _env_file=None,
    )
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ProvidersSubsystem())
    kernel.register(MissionsSubsystem(missions_dir=tmp_path / "missions"))
    kernel.register(AgentsSubsystem())
    ctx = await kernel.start()
    try:
        report = await kernel.health()
        names = {s["name"] for s in report["subsystems"]}
        assert {"heartbeat", "providers", "missions"} <= names
        assert ctx.provider_router is not None
        assert ctx.mission_runtime is not None
        created = await ctx.mission_runtime.create(
            MissionSpec(goal="Index repo. Run tests. Summarize.")
        )
        finished = await ctx.mission_runtime.start(created.mission_id)
        assert finished.status == MissionStatus.SUCCEEDED
        assert len(finished.all_tasks()) == 3
    finally:
        await kernel.stop()
