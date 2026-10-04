"""Deep unit coverage for expanded M3 agent runtime."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from emily.agents.analytics import AgentAnalytics
from emily.agents.errors import AgentCapacityError, AgentError
from emily.agents.factory import WorkerFactory
from emily.agents.history import AgentHistoryStore
from emily.agents.llm_worker import LLMWorker
from emily.agents.models import AgentInstance, AgentTaskRequest, PipelineStep, VerificationVerdict
from emily.agents.pool import AgentPool
from emily.agents.registry import AgentRegistry
from emily.agents.supervisor import AgentSupervisor
from emily.agents.team import AgentTeam
from emily.agents.verification import VerificationLoop
from emily.agents.workers import SpecializedWorker, VerificationWorker
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


def test_registry_expanded_inference() -> None:
    registry = AgentRegistry()
    assert registry.infer_kind("Security threat model for auth") == AgentKind.SECURITY
    assert registry.infer_kind("Monitor uptime SLO") == AgentKind.MONITORING
    assert registry.infer_kind("Remember this memory note") == AgentKind.MEMORY
    assert registry.infer_kind("Browser navigate checkout") == AgentKind.BROWSER
    assert len(registry.list_roles()) >= 12


@pytest.mark.asyncio
async def test_specialized_worker_disabled() -> None:
    agent = AgentInstance(kind=AgentKind.CODING, status=AgentStatus.RUNNING)
    with pytest.raises(AgentError, match="disabled"):
        await SpecializedWorker(AgentKind.CODING).run(
            agent,
            AgentTaskRequest(
                title="Implement login",
                description="Add OAuth",
            ),
        )


@pytest.mark.asyncio
async def test_llm_worker_uses_complete() -> None:
    class Router:
        async def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            assert messages[0]["role"] == "system"
            return "implemented oauth login flow with tests"

    agent = AgentInstance(kind=AgentKind.CODING, status=AgentStatus.RUNNING)
    out = await LLMWorker(AgentKind.CODING, router=Router()).run(
        agent,
        AgentTaskRequest(title="Implement login", description="Add OAuth"),
    )
    assert "oauth" in out.lower()


@pytest.mark.asyncio
async def test_verification_criteria_and_score() -> None:
    verifier = VerificationWorker()
    decision = verifier.decide(
        AgentTaskRequest(
            title="Verify",
            acceptance_criteria=["alpha-token", "beta-token"],
            metadata={"candidate_output": "result includes alpha-token and beta-token"},
        )
    )
    assert decision.verdict == VerificationVerdict.ACCEPT
    assert decision.score >= 0.7

    rejected = verifier.decide(
        AgentTaskRequest(
            title="Verify",
            acceptance_criteria=["missing-needle"],
            metadata={"candidate_output": "completely unrelated output text"},
        )
    )
    assert rejected.verdict == VerificationVerdict.REJECT
    assert "missing-needle" in rejected.reason


@pytest.mark.asyncio
async def test_critique_feedback_retry_succeeds() -> None:
    class ImproveOnce(SpecializedWorker):
        def __init__(self) -> None:
            super().__init__(AgentKind.CUSTOM)
            self.calls = 0

        async def run(self, agent, request):  # type: ignore[no-untyped-def]
            self.calls += 1
            if self.calls == 1:
                return "failed"
            return "completed successfully with enough detail"

    loop = VerificationLoop()
    worker = ImproveOnce()
    result = await loop.run(
        work_agent_id="agt_retry",
        work_kind=AgentKind.CUSTOM,
        request=AgentTaskRequest(title="Retry me"),
        max_retries=2,
        work_worker=worker,
    )
    assert result.success is True
    assert result.attempts == 2
    assert result.critique_trail
    assert result.decision is not None


@pytest.mark.asyncio
async def test_pipeline_handoff_and_goal() -> None:
    team = AgentTeam(_supervisor())
    result = await team.run_pipeline(
        [
            PipelineStep(title="Research market", kind=AgentKind.RESEARCH),
            PipelineStep(title="Draft brief", kind=AgentKind.DOCUMENT, handoff=True),
        ]
    )
    assert result.success is True
    assert "Prior handoff" in result.steps[1].output or "research:" in result.steps[0].output.lower()

    goal = await team.run_goal_pipeline("Research competitors. Draft summary.")
    assert goal.success is True
    assert len(goal.steps) >= 3  # includes trailing verification


@pytest.mark.asyncio
async def test_fanout_parallel() -> None:
    team = AgentTeam(_supervisor(pool=AgentPool(max_concurrent=4)))
    results = await team.run_fanout(
        [
            AgentTaskRequest(title="Analyze CSV", kind=AgentKind.DATA),
            AgentTaskRequest(title="Security review", kind=AgentKind.SECURITY),
            AgentTaskRequest(title="Health diagnostic monitor", kind=AgentKind.MONITORING),
        ]
    )
    assert len(results) == 3
    assert all(r.success for r in results)


@pytest.mark.asyncio
async def test_pool_timeout_raises() -> None:
    pool = AgentPool(max_concurrent=1)

    async def hold() -> None:
        async with pool.acquire(wait_timeout=1.0):
            await asyncio.sleep(0.3)

    task = asyncio.create_task(hold())
    await asyncio.sleep(0.05)
    with pytest.raises(AgentCapacityError):
        async with pool.acquire(wait_timeout=0.05):
            pass
    await task


@pytest.mark.asyncio
async def test_analytics_and_history(tmp_path: Path) -> None:
    analytics = AgentAnalytics()
    history = AgentHistoryStore(tmp_path)
    supervisor = _supervisor(analytics=analytics, history=history)
    await supervisor.run_task(AgentTaskRequest(title="Research X", kind=AgentKind.RESEARCH))
    await supervisor.run_task(AgentTaskRequest(title="Draft Y", kind=AgentKind.DOCUMENT))
    summary = analytics.summary()
    assert summary["runs"] == 2
    assert summary["successes"] == 2
    assert "research" in summary["by_kind"]
    records = await history.list_runs()
    assert len(records) == 2
    cleared = await history.clear()
    assert cleared == 2


@pytest.mark.asyncio
async def test_event_stream_includes_started_verified() -> None:
    bus = InProcessEventBus()
    await bus.start()
    seen: list[str] = []

    async def capture(event_type: str, _payload: dict[str, object]) -> None:
        seen.append(event_type)

    bus.subscribe("agent.*", capture)
    supervisor = _supervisor(event_bus=bus)
    await supervisor.run_task(AgentTaskRequest(title="Implement feature", kind=AgentKind.CODING))
    await bus.stop()
    assert "agent.started" in seen
    assert "agent.verified" in seen
    assert "agent.completed" in seen


@pytest.mark.asyncio
async def test_llm_worker_fallback() -> None:
    class Boom:
        async def complete(self, *_a, **_k):  # type: ignore[no-untyped-def]
            raise RuntimeError("provider down")

    worker = LLMWorker(AgentKind.RESEARCH, router=Boom(), timeout_seconds=1.0)
    with pytest.raises(AgentError, match="LLM worker failed"):
        await worker.run(
            AgentInstance(kind=AgentKind.RESEARCH),
            AgentTaskRequest(title="Research topic", description="details"),
        )


@pytest.mark.asyncio
async def test_llm_worker_success_path() -> None:
    class Ok:
        async def achat(self, *_a, **_k):  # type: ignore[no-untyped-def]
            return {"content": "llm answer body"}

    worker = LLMWorker(AgentKind.CUSTOM, router=Ok())
    out = await worker.run(
        AgentInstance(kind=AgentKind.CUSTOM),
        AgentTaskRequest(title="Hello"),
    )
    assert "llm answer body" in out


@pytest.mark.asyncio
async def test_factory_llm_flag() -> None:
    class Ok:
        async def complete(self, *_a, **_k):  # type: ignore[no-untyped-def]
            return "from-factory"

    factory = WorkerFactory(use_llm=True, router=Ok())
    worker = factory.create(AgentKind.DOCUMENT)
    out = await worker.run(
        AgentInstance(kind=AgentKind.DOCUMENT),
        AgentTaskRequest(title="Draft"),
    )
    assert "from-factory" in out

    with pytest.raises(AgentError, match="provider router required"):
        WorkerFactory(use_llm=False).create(AgentKind.DOCUMENT)


@pytest.mark.asyncio
async def test_verification_as_work_uses_prior() -> None:
    loop = VerificationLoop()
    accepted = await loop.run(
        work_agent_id="v1",
        work_kind=AgentKind.VERIFICATION,
        request=AgentTaskRequest(
            title="Verify packet",
            prior_output="completed successfully with rich detail",
        ),
    )
    assert accepted.success is True
    rejected = await loop.run(
        work_agent_id="v2",
        work_kind=AgentKind.VERIFICATION,
        request=AgentTaskRequest(title="Verify empty", prior_output=""),
    )
    assert rejected.success is False


@pytest.mark.asyncio
async def test_run_on_agent_reuses_instance() -> None:
    supervisor = _supervisor()
    agent = await supervisor.spawn(AgentKind.DATA)
    result = await supervisor.run_on_agent(
        agent.agent_id,
        AgentTaskRequest(title="Analyze metrics", description="csv"),
    )
    assert result.success is True
    assert agent.run_count == 1
    assert supervisor.get(agent.agent_id).status == AgentStatus.IDLE
