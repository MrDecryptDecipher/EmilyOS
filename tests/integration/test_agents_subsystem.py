"""Kernel integration for agents subsystem."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from emily.agents.models import AgentTaskRequest
from emily.agents.subsystem import AgentsSubsystem
from emily.config.settings import EmilySettings
from emily.core.types.mission import MissionStatus
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.missions.models import MissionSpec
from emily.missions.subsystem import MissionsSubsystem
from emily.providers.subsystem import ProvidersSubsystem


@pytest.mark.asyncio
async def test_agents_subsystem_wires_mission_executor(tmp_path: Path) -> None:
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
        assert ctx.agent_supervisor is not None
        assert ctx.mission_runtime is not None
        assert ctx.mission_runtime.executor_slot.executor is not None
        result = await ctx.agent_supervisor.run_task(
            AgentTaskRequest(title="Code review helper", description="Review diff")
        )
        assert result.success is True
        created = await ctx.mission_runtime.create(
            MissionSpec(goal="Implement feature. Verify behavior.")
        )
        finished = await ctx.mission_runtime.start(created.mission_id)
        assert finished.status == MissionStatus.SUCCEEDED
        assert all(t.metadata.get("agent_id") for t in finished.all_tasks())
    finally:
        await kernel.stop()
        assert ctx.agent_supervisor is None
