"""Agent supervisor — spawn, run, terminate, observe."""

from __future__ import annotations

from typing import Any

from emily.agents.analytics import AgentAnalytics
from emily.agents.errors import AgentNotFoundError, AgentStateError
from emily.agents.factory import WorkerFactory
from emily.agents.history import AgentHistoryStore
from emily.agents.models import AgentInstance, AgentRunResult, AgentTaskRequest
from emily.agents.pool import AgentPool
from emily.agents.registry import AgentRegistry
from emily.agents.verification import VerificationLoop
from emily.core.types.agent import AgentKind, AgentStatus


class AgentSupervisor:
    """Process-local supervisor for dynamic agents."""

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        *,
        event_bus: Any | None = None,
        logger: Any | None = None,
        pool: AgentPool | None = None,
        analytics: AgentAnalytics | None = None,
        history: AgentHistoryStore | None = None,
        worker_factory: WorkerFactory | None = None,
        acquire_timeout: float | None = 30.0,
    ) -> None:
        self.registry = registry or AgentRegistry()
        self.event_bus = event_bus
        self.logger = logger
        self.pool = pool or AgentPool()
        self.analytics = analytics or AgentAnalytics()
        self.history = history
        self.worker_factory = worker_factory or WorkerFactory()
        self.acquire_timeout = acquire_timeout
        self._agents: dict[str, AgentInstance] = {}
        self._verification = VerificationLoop(self.registry)

    def list_agents(self, *, include_terminated: bool = False) -> list[AgentInstance]:
        agents = list(self._agents.values())
        if include_terminated:
            return sorted(agents, key=lambda a: a.created_at)
        return sorted(
            [a for a in agents if a.status != AgentStatus.TERMINATED],
            key=lambda a: a.created_at,
        )

    def get(self, agent_id: str) -> AgentInstance:
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise AgentNotFoundError(agent_id) from exc

    async def spawn(
        self,
        kind: AgentKind,
        *,
        mission_id: str | None = None,
        task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentInstance:
        self.registry.get(kind)  # validate
        agent = AgentInstance(
            kind=kind,
            status=AgentStatus.SPAWNING,
            mission_id=mission_id,
            task_id=task_id,
            metadata=dict(metadata or {}),
        )
        self._agents[agent.agent_id] = agent
        agent.status = AgentStatus.IDLE
        agent.touch()
        await self._emit("agent.spawned", agent)
        if self.logger is not None:
            self.logger.info("agent spawned", agent_id=agent.agent_id, kind=kind.value)
        return agent

    async def terminate(self, agent_id: str) -> AgentInstance:
        agent = self.get(agent_id)
        if agent.status == AgentStatus.TERMINATED:
            return agent
        if agent.status == AgentStatus.RUNNING:
            agent.status = AgentStatus.WAITING
            agent.touch()
        agent.status = AgentStatus.TERMINATED
        agent.touch()
        await self._emit("agent.terminated", agent)
        return agent

    async def run_task(self, request: AgentTaskRequest) -> AgentRunResult:
        kind = request.kind or self.registry.infer_kind(request.title, request.description)
        agent = await self.spawn(
            kind,
            mission_id=request.mission_id,
            task_id=request.task_id,
            metadata=dict(request.metadata),
        )
        try:
            result = await self._execute(agent, request.model_copy(update={"kind": kind}))
            return result
        finally:
            await self.terminate(agent.agent_id)

    async def run_on_agent(self, agent_id: str, request: AgentTaskRequest) -> AgentRunResult:
        agent = self.get(agent_id)
        if agent.status == AgentStatus.TERMINATED:
            raise AgentStateError("cannot run task on terminated agent", agent_id=agent_id)
        if agent.status == AgentStatus.RUNNING:
            raise AgentStateError("agent already running", agent_id=agent_id)
        return await self._execute(
            agent,
            request.model_copy(update={"kind": agent.kind}),
        )

    async def _execute(self, agent: AgentInstance, request: AgentTaskRequest) -> AgentRunResult:
        async with self.pool.acquire(wait_timeout=self.acquire_timeout):
            await self._emit("agent.started", agent, extra={"title": request.title})

            async def _set_status(status: AgentStatus) -> None:
                agent.status = status
                agent.touch()

            async def _on_event(event_type: str, payload: dict[str, Any]) -> None:
                if self.event_bus is None:
                    return
                await self.event_bus.publish(event_type, payload, source="agents")

            result = await self._verification.run(
                work_agent_id=agent.agent_id,
                work_kind=agent.kind,
                request=request,
                work_worker=self.worker_factory.create(agent.kind),
                on_status=_set_status,
                on_event=_on_event,
            )
            result.metadata = {
                **result.metadata,
                "mission_id": request.mission_id,
                "task_id": request.task_id,
                "title": request.title,
            }
            agent.run_count += 1
            if result.success:
                agent.last_error = None
                agent.status = AgentStatus.IDLE
                agent.touch()
                await self._emit("agent.completed", agent, extra={"attempts": result.attempts})
            else:
                agent.last_error = result.error
                agent.status = AgentStatus.FAILED
                agent.touch()
                await self._emit("agent.failed", agent, extra={"error": result.error})

            self.analytics.record(result)
            if self.history is not None:
                await self.history.record(result, title=request.title)
            if self.logger is not None:
                self.logger.info(
                    "agent run finished",
                    agent_id=agent.agent_id,
                    kind=agent.kind.value,
                    success=result.success,
                    attempts=result.attempts,
                    latency_ms=result.latency_ms,
                )
            return result

    async def _emit(
        self,
        event_type: str,
        agent: AgentInstance,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if self.event_bus is None:
            return
        payload: dict[str, Any] = {
            "agent_id": agent.agent_id,
            "kind": agent.kind.value,
            "status": agent.status.value,
            "mission_id": agent.mission_id,
            "task_id": agent.task_id,
        }
        if extra:
            payload.update(extra)
        await self.event_bus.publish(event_type, payload, source="agents")
