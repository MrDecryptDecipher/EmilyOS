"""Kernel subsystem for agent runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from emily.agents.analytics import AgentAnalytics
from emily.agents.executor import AgentTaskExecutor
from emily.agents.factory import WorkerFactory
from emily.agents.history import AgentHistoryStore
from emily.agents.pool import AgentPool
from emily.agents.registry import AgentRegistry
from emily.agents.supervisor import AgentSupervisor
from emily.agents.team import AgentTeam
from emily.core.types.common import HealthStatus, SubsystemState
from emily.kernel.context import DefaultKernelContext
from emily.kernel.subsystem import BaseSubsystem


class AgentsSubsystem(BaseSubsystem):
    name = "agents"
    startup_priority = 40
    shutdown_priority = 25

    def __init__(self, *, history_dir: Path | str | None = None) -> None:
        super().__init__()
        self.supervisor: AgentSupervisor | None = None
        self.team: AgentTeam | None = None
        self.registry = AgentRegistry()
        self._history_dir_override = Path(history_dir) if history_dir is not None else None

    async def on_start(self, ctx: Any) -> None:
        if not isinstance(ctx, DefaultKernelContext):
            raise TypeError("AgentsSubsystem requires DefaultKernelContext")

        settings = ctx.settings
        max_concurrent = int(getattr(settings, "agent_max_concurrent", 8))
        use_llm = bool(getattr(settings, "agent_llm_workers", True))
        timeout = float(getattr(settings, "agent_llm_timeout_seconds", 45.0))
        history_enabled = bool(getattr(settings, "agent_history_enabled", True))
        history_dir = self._history_dir_override or Path(
            getattr(settings, "agent_history_directory", Path("data/agents"))
        )

        history = AgentHistoryStore(history_dir) if history_enabled else None
        factory = WorkerFactory(
            use_llm=use_llm,
            router=ctx.provider_router if use_llm else None,
            timeout_seconds=timeout,
            memory=ctx.memory_runtime,
            desktop=getattr(ctx, "desktop_runtime", None),
            browser=getattr(ctx, "browser_runtime", None),
            voice=getattr(ctx, "voice_runtime", None),
            tools=ctx.tool_runtime,
        )
        self.supervisor = AgentSupervisor(
            self.registry,
            event_bus=ctx.event_bus,
            logger=ctx.logger,
            pool=AgentPool(max_concurrent=max_concurrent),
            analytics=AgentAnalytics(),
            history=history,
            worker_factory=factory,
            acquire_timeout=float(getattr(settings, "agent_pool_timeout_seconds", 30.0)),
        )
        self.team = AgentTeam(self.supervisor)
        ctx.agent_supervisor = self.supervisor
        ctx.extras["agent_team"] = self.team

        if ctx.mission_runtime is not None:
            ctx.mission_runtime.set_task_executor(AgentTaskExecutor(self.supervisor))
        ctx.logger.info(
            "agents subsystem started",
            roles=len(self.registry.list_roles()),
            max_concurrent=max_concurrent,
            llm_workers=use_llm and ctx.provider_router is not None,
            history=str(history_dir) if history is not None else None,
            memory=ctx.memory_runtime is not None,
            desktop=getattr(ctx, "desktop_runtime", None) is not None,
        )

    async def on_stop(self, ctx: Any) -> None:
        if self.supervisor is not None:
            for agent in self.supervisor.list_agents(include_terminated=False):
                await self.supervisor.terminate(agent.agent_id)
        if isinstance(ctx, DefaultKernelContext):
            if ctx.mission_runtime is not None:
                ctx.mission_runtime.set_task_executor(None)
            summary = (
                self.supervisor.analytics.summary() if self.supervisor is not None else {}
            )
            ctx.logger.info("agents subsystem stopped", analytics=summary)
            ctx.agent_supervisor = None
            if isinstance(getattr(ctx, "extras", None), dict):
                ctx.extras.pop("agent_team", None)
        self.supervisor = None
        self.team = None

    async def health(self) -> HealthStatus:
        active = 0
        pool_active = 0
        pool_max = 0
        runs = 0
        successes = 0
        if self.supervisor is not None:
            active = len(self.supervisor.list_agents(include_terminated=False))
            snap = self.supervisor.pool.snapshot()
            pool_active = int(snap["active"])
            pool_max = int(snap["max_concurrent"])
            summary = self.supervisor.analytics.summary()
            runs = int(summary["runs"])
            successes = int(summary["successes"])
        return HealthStatus(
            name=self.name,
            healthy=self._state == SubsystemState.RUNNING and self.supervisor is not None,
            state=self._state,
            message="ready" if self.supervisor is not None else "not initialized",
            details={
                "active_agents": active,
                "pool_active": pool_active,
                "pool_max": pool_max,
                "runs": runs,
                "successes": successes,
            },
        )
