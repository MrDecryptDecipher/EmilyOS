"""Supervisor and verification loop tests."""

from __future__ import annotations

from typing import Any

import pytest

from emily.agents.errors import AgentNotFoundError, AgentStateError
from emily.agents.factory import WorkerFactory
from emily.agents.models import AgentTaskRequest
from emily.agents.supervisor import AgentSupervisor
from emily.agents.verification import VerificationLoop
from emily.agents.workers import HeuristicWorker
from emily.core.types.agent import AgentKind, AgentStatus
from emily.events.bus import InProcessEventBus


class _ScriptedRouter:
    async def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        return f"completed: {messages[-1]['content'][:200]}"


def _supervisor(**kwargs: Any) -> AgentSupervisor:
    return AgentSupervisor(
        worker_factory=WorkerFactory(use_llm=True, router=_ScriptedRouter()),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_spawn_run_terminate_lifecycle() -> None:
    supervisor = _supervisor()
    agent = await supervisor.spawn(AgentKind.CODING)
    assert agent.status == AgentStatus.IDLE
    assert supervisor.get(agent.agent_id).agent_id == agent.agent_id
    result = await supervisor.run_on_agent(
        agent.agent_id,
        AgentTaskRequest(title="Implement feature", description="Add endpoint"),
    )
    assert result.success is True
    assert result.attempts >= 1
    terminated = await supervisor.terminate(agent.agent_id)
    assert terminated.status == AgentStatus.TERMINATED
    assert supervisor.list_agents() == []


@pytest.mark.asyncio
async def test_run_task_spawns_and_destroys() -> None:
    bus = InProcessEventBus()
    await bus.start()
    seen: list[str] = []

    async def capture(event_type: str, _payload: dict[str, object]) -> None:
        seen.append(event_type)

    bus.subscribe("agent.*", capture)
    supervisor = _supervisor(event_bus=bus)
    result = await supervisor.run_task(
        AgentTaskRequest(title="Research competitors", description="Find top 3")
    )
    await bus.stop()
    assert result.success is True
    assert result.kind == AgentKind.RESEARCH
    assert "agent.spawned" in seen
    assert "agent.terminated" in seen
    assert supervisor.list_agents() == []


@pytest.mark.asyncio
async def test_verification_retries_then_fails() -> None:
    class AlwaysBad(HeuristicWorker):
        async def run(self, agent, request):  # type: ignore[no-untyped-def]
            return "failed"

    loop = VerificationLoop()
    result = await loop.run(
        work_agent_id="agt_bad",
        work_kind=AgentKind.CUSTOM,
        request=AgentTaskRequest(title="Bad"),
        max_retries=1,
        work_worker=AlwaysBad(AgentKind.CUSTOM),
    )
    assert result.success is False
    assert result.attempts == 2
    assert result.error is not None


@pytest.mark.asyncio
async def test_supervisor_guards() -> None:
    supervisor = _supervisor()
    with pytest.raises(AgentNotFoundError):
        supervisor.get("missing")
    agent = await supervisor.spawn(AgentKind.CUSTOM)
    await supervisor.terminate(agent.agent_id)
    with pytest.raises(AgentStateError):
        await supervisor.run_on_agent(
            agent.agent_id,
            AgentTaskRequest(title="x", description="y"),
        )
