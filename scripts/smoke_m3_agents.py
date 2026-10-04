"""Milestone 3 smoke harness — real worker paths (scripted provider for offline CI)."""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from emily.agents.analytics import AgentAnalytics
from emily.agents.errors import AgentCapacityError
from emily.agents.executor import AgentTaskExecutor
from emily.agents.factory import WorkerFactory
from emily.agents.history import AgentHistoryStore
from emily.agents.models import AgentTaskRequest, PipelineStep
from emily.agents.pool import AgentPool
from emily.agents.supervisor import AgentSupervisor
from emily.agents.team import AgentTeam
from emily.agents.workers import SpecializedWorker
from emily.core.types.agent import AgentKind
from emily.core.types.mission import MissionStatus
from emily.events.bus import InProcessEventBus
from emily.missions.models import MissionSpec
from emily.missions.runtime import MissionRuntime
from emily.missions.store import MissionStore


@dataclass
class ProbeResult:
    name: str
    ok: bool
    detail: str


class _ScriptedRouter:
    """Deterministic provider stand-in for offline smoke (not production)."""

    async def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        user = messages[-1]["content"] if messages else ""
        return f"completed analysis for: {user[:240]}"


def _supervisor(**kwargs: Any) -> AgentSupervisor:
    factory = WorkerFactory(use_llm=True, router=_ScriptedRouter(), timeout_seconds=10.0)
    return AgentSupervisor(worker_factory=factory, **kwargs)


async def probe_specialized_kinds() -> ProbeResult:
    supervisor = _supervisor()
    kinds = [
        AgentKind.RESEARCH,
        AgentKind.CODING,
        AgentKind.DOCUMENT,
        AgentKind.DATA,
        AgentKind.SECURITY,
        AgentKind.MONITORING,
    ]
    results = []
    for kind in kinds:
        result = await supervisor.run_task(
            AgentTaskRequest(title=f"{kind.value} probe", description="probe body", kind=kind)
        )
        results.append(result.success and kind.value in result.output.lower())
    ok = all(results)
    return ProbeResult("agent:llm_kinds", ok, f"passed={sum(results)}/{len(kinds)}")


async def probe_critique_retry() -> ProbeResult:
    class Flaky(SpecializedWorker):
        def __init__(self) -> None:
            super().__init__(AgentKind.CUSTOM)
            self.n = 0

        async def run(self, agent, request):  # type: ignore[no-untyped-def]
            self.n += 1
            if self.n == 1:
                return "failed"
            return "completed successfully with enough detail for verification"

    supervisor = _supervisor()
    flaky = Flaky()
    supervisor.worker_factory.register(AgentKind.CUSTOM, lambda _k: flaky)
    result = await supervisor.run_task(
        AgentTaskRequest(title="Recoverable", description="should pass on retry", kind=AgentKind.CUSTOM)
    )
    return ProbeResult(
        "agent:critique_retry",
        result.success and result.attempts == 2 and bool(result.critique_trail),
        f"success={result.success} attempts={result.attempts} critiques={result.critique_trail}",
    )


async def probe_team_pipeline() -> ProbeResult:
    supervisor = _supervisor()
    team = AgentTeam(supervisor)
    result = await team.run_pipeline(
        [
            PipelineStep(kind=AgentKind.RESEARCH, title="Research", description="topic"),
            PipelineStep(kind=AgentKind.DOCUMENT, title="Draft", description="write"),
            PipelineStep(kind=AgentKind.VERIFICATION, title="Verify", description="check"),
        ]
    )
    return ProbeResult(
        "agent:pipeline",
        result.success and len(result.steps) == 3,
        f"success={result.success} steps={len(result.steps)}",
    )


async def probe_mission_executor(root: Path) -> ProbeResult:
    store = MissionStore(root / "missions")
    runtime = MissionRuntime(store)
    supervisor = _supervisor()
    runtime.set_task_executor(AgentTaskExecutor(supervisor))
    created = await runtime.create(MissionSpec(goal="Research. Draft. Verify."))
    finished = await runtime.start(created.mission_id)
    ok = finished.status == MissionStatus.SUCCEEDED
    return ProbeResult("agent:mission_executor", ok, f"status={finished.status}")


async def probe_pool_and_history(root: Path) -> ProbeResult:
    history = AgentHistoryStore(root / "history")
    supervisor = _supervisor(
        pool=AgentPool(max_concurrent=1),
        analytics=AgentAnalytics(),
        history=history,
        acquire_timeout=0.1,
    )
    # Saturate pool
    async def hold() -> None:
        await supervisor.run_task(AgentTaskRequest(title="hold", description="x", kind=AgentKind.CUSTOM))

    # Custom worker that sleeps
    class Slow(SpecializedWorker):
        async def run(self, agent, request):  # type: ignore[no-untyped-def]
            await asyncio.sleep(0.5)
            return "completed slowly with enough detail"

    supervisor.worker_factory.register(AgentKind.CUSTOM, lambda _k: Slow(AgentKind.CUSTOM))
    task = asyncio.create_task(hold())
    await asyncio.sleep(0.05)
    denied = False
    try:
        await supervisor.run_task(AgentTaskRequest(title="blocked", description="y", kind=AgentKind.CUSTOM))
    except AgentCapacityError:
        denied = True
    await task
    runs = await history.list_runs(limit=10)
    return ProbeResult(
        "agent:pool_history",
        denied and len(runs) >= 1,
        f"denied={denied} runs={len(runs)}",
    )


async def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="emily-m3-"))
    probes = [
        await probe_specialized_kinds(),
        await probe_critique_retry(),
        await probe_team_pipeline(),
        await probe_mission_executor(root),
        await probe_pool_and_history(root),
    ]
    width = max(len(p.name) for p in probes)
    passed = 0
    for probe in probes:
        mark = "PASS" if probe.ok else "FAIL"
        print(f"[{mark}] {probe.name:<{width}}  {probe.detail}")
        if probe.ok:
            passed += 1
    print(f"\n{passed}/{len(probes)} probes passed")
    return 0 if passed == len(probes) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
