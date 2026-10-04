"""Deep e2e / integration tests for Milestone 3 agent runtime."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import SecretStr

from emily.agents.executor import AgentTaskExecutor
from emily.agents.models import AgentTaskRequest
from emily.agents.pool import AgentPool
from emily.agents.subsystem import AgentsSubsystem
from emily.agents.supervisor import AgentSupervisor
from emily.agents.team import AgentTeam
from emily.config.settings import EmilySettings
from emily.core.types.agent import AgentKind
from emily.core.types.mission import MissionStatus
from emily.events.bus import InProcessEventBus
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.missions.models import MissionSpec, TaskStatus
from emily.missions.runtime import MissionRuntime
from emily.missions.store import MissionStore
from emily.missions.subsystem import MissionsSubsystem
from emily.providers.subsystem import ProvidersSubsystem


def _settings(**kwargs: object) -> EmilySettings:
    base = {
        "environment": "test",
        "log_level": "ERROR",
        "nvidia_api_key": SecretStr(""),
        "routesme_api_key": SecretStr(""),
        "mission_llm_planner": False,
        "agent_llm_workers": False,
        "agent_history_enabled": True,
        "_env_file": None,
    }
    base.update(kwargs)
    return EmilySettings(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_kernel_agents_mission_full_stack(tmp_path: Path) -> None:
    settings = _settings(agent_history_directory=tmp_path / "agents")
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ProvidersSubsystem())
    kernel.register(MissionsSubsystem(missions_dir=tmp_path / "missions"))
    kernel.register(AgentsSubsystem(history_dir=tmp_path / "agents"))
    ctx = await kernel.start()
    try:
        assert ctx.agent_supervisor is not None
        assert ctx.get_extra("agent_team") is not None
        health = await kernel.health()
        agents_report = next(s for s in health["subsystems"] if s["name"] == "agents")
        assert agents_report["healthy"] is True
        assert agents_report["details"]["pool_max"] >= 1

        team: AgentTeam = ctx.get_extra("agent_team")
        pipeline = await team.run_goal_pipeline(
            "Research market. Draft summary. Implement tracker."
        )
        assert pipeline.success is True

        created = await ctx.mission_runtime.create(  # type: ignore[union-attr]
            MissionSpec(goal="Analyze CSV metrics. Draft data report. Verify findings.")
        )
        finished = await ctx.mission_runtime.start(created.mission_id)  # type: ignore[union-attr]
        assert finished.status == MissionStatus.SUCCEEDED
        for task in finished.all_tasks():
            assert task.status == TaskStatus.SUCCEEDED
            assert task.metadata.get("agent_id")
            assert task.metadata.get("agent_kind")
            assert task.metadata.get("verification")
            assert task.metadata.get("attempts", 0) >= 1

        summary = ctx.agent_supervisor.analytics.summary()
        assert summary["runs"] >= 3
        assert summary["failures"] == 0

        history = await ctx.agent_supervisor.history.list_runs()  # type: ignore[union-attr]
        assert len(history) >= 3
    finally:
        await kernel.stop()


@pytest.mark.asyncio
async def test_mission_with_acceptance_criteria_metadata(tmp_path: Path) -> None:
    runtime = MissionRuntime(MissionStore(tmp_path))
    supervisor = AgentSupervisor()
    runtime.set_task_executor(AgentTaskExecutor(supervisor))
    created = await runtime.create(MissionSpec(goal="Draft outline document"))
    # Inject criteria into planned tasks via direct execute path.
    updated = await AgentTaskExecutor(supervisor).execute_task(
        mission_id=created.mission_id,
        task={
            "task_id": "tsk_criteria",
            "title": "Draft outline document",
            "description": "Write outline",
            "status": TaskStatus.READY.value,
            "depends_on": [],
            "metadata": {
                "agent_kind": "document",
                "acceptance_criteria": ["outline", "document"],
            },
        },
    )
    assert updated["status"] == TaskStatus.SUCCEEDED.value
    assert updated["metadata"]["verification_verdict"] == "ACCEPT"
    assert updated["metadata"]["verification_score"] > 0


@pytest.mark.asyncio
async def test_concurrent_agent_missions_under_pool(tmp_path: Path) -> None:
    runtime = MissionRuntime(MissionStore(tmp_path))
    supervisor = AgentSupervisor(pool=AgentPool(max_concurrent=3), acquire_timeout=5.0)
    runtime.set_task_executor(AgentTaskExecutor(supervisor))

    async def run_one(goal: str) -> MissionStatus:
        created = await runtime.create(MissionSpec(goal=goal))
        finished = await runtime.start(created.mission_id)
        return finished.status

    statuses = await asyncio.gather(
        run_one("Research A. Draft A."),
        run_one("Research B. Draft B."),
        run_one("Implement C. Verify C."),
        run_one("Analyze D. Draft D."),
    )
    assert all(s == MissionStatus.SUCCEEDED for s in statuses)
    assert supervisor.analytics.summary()["successes"] >= 8


@pytest.mark.asyncio
async def test_event_lifecycle_under_kernel(tmp_path: Path) -> None:
    bus = InProcessEventBus()
    await bus.start()
    seen: list[str] = []

    async def capture(event_type: str, _payload: dict[str, object]) -> None:
        seen.append(event_type)

    bus.subscribe("agent.*", capture)
    settings = _settings(agent_history_directory=tmp_path / "hist")
    kernel = ExecutiveKernel(settings=settings)
    # Replace bus after construction is awkward; drive supervisor directly with kernel settings path.
    supervisor = AgentSupervisor(event_bus=bus)
    await supervisor.run_task(
        AgentTaskRequest(title="Security threat review", kind=AgentKind.SECURITY)
    )
    await bus.stop()
    assert "agent.spawned" in seen
    assert "agent.started" in seen
    assert "agent.verified" in seen
    assert "agent.completed" in seen
    assert "agent.terminated" in seen
    _ = kernel  # keep import usage intentional for future wiring
