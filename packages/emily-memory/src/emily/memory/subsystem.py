"""Kernel subsystem for memory & world model."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from emily.core.types.common import HealthStatus, SubsystemState
from emily.core.types.memory import MemoryKind
from emily.kernel.context import DefaultKernelContext
from emily.kernel.subsystem import BaseSubsystem
from emily.memory.models import MemoryWrite, ObservedRelation, WorldObservation
from emily.memory.runtime import MemoryRuntime


class MemorySubsystem(BaseSubsystem):
    name = "memory"
    startup_priority = 25
    shutdown_priority = 35

    def __init__(
        self,
        *,
        memory_dir: Path | str | None = None,
        world_dir: Path | str | None = None,
    ) -> None:
        super().__init__()
        self.runtime: MemoryRuntime | None = None
        self._memory_dir_override = Path(memory_dir) if memory_dir is not None else None
        self._world_dir_override = Path(world_dir) if world_dir is not None else None
        self._disabled = False

    async def on_start(self, ctx: Any) -> None:
        if not isinstance(ctx, DefaultKernelContext):
            raise TypeError("MemorySubsystem requires DefaultKernelContext")
        if not bool(getattr(ctx.settings, "memory_enabled", True)):
            self._disabled = True
            ctx.logger.info("memory subsystem skipped (disabled)")
            return

        memory_dir = self._memory_dir_override or Path(
            getattr(ctx.settings, "memory_directory", Path("data/memory"))
        )
        world_dir = self._world_dir_override or Path(
            getattr(ctx.settings, "world_directory", Path("data/world"))
        )
        limit = int(getattr(ctx.settings, "memory_retrieval_limit", 8))
        self.runtime = MemoryRuntime(
            memory_dir,
            world_dir,
            event_bus=ctx.event_bus,
            logger=ctx.logger,
            default_limit=limit,
        )
        await self.runtime.start()
        ctx.memory_runtime = self.runtime
        ctx.extras["memory_runtime"] = self.runtime
        self._subscribe_events(ctx)
        ctx.logger.info(
            "memory subsystem started",
            memory_dir=str(memory_dir),
            world_dir=str(world_dir),
        )

    async def on_stop(self, ctx: Any) -> None:
        if self.runtime is not None:
            await self.runtime.stop()
        if isinstance(ctx, DefaultKernelContext):
            stats = await self.runtime.stats() if self.runtime is not None else {}
            ctx.logger.info("memory subsystem stopped", stats=stats)
            ctx.memory_runtime = None
            ctx.extras.pop("memory_runtime", None)
        self.runtime = None

    async def health(self) -> HealthStatus:
        if self._disabled:
            return HealthStatus(
                name=self.name,
                healthy=True,
                state=self._state,
                message="disabled",
                details={"memory_total": 0, "world_entities": 0},
            )
        total = 0
        entities = 0
        if self.runtime is not None:
            stats = await self.runtime.stats()
            total = int(stats.get("memory_total", 0))
            entities = int(stats.get("world_entities", 0))
        return HealthStatus(
            name=self.name,
            healthy=self._state == SubsystemState.RUNNING and self.runtime is not None,
            state=self._state,
            message="ready" if self.runtime is not None else "not initialized",
            details={"memory_total": total, "world_entities": entities},
        )

    def _subscribe_events(self, ctx: DefaultKernelContext) -> None:
        runtime = self.runtime
        if runtime is None:
            return

        async def on_mission(event_type: str, payload: Mapping[str, Any]) -> None:
            mission_id = str(payload.get("mission_id") or "")
            status = str(payload.get("status") or event_type)
            goal = str(payload.get("goal") or "")
            content = f"Mission event {event_type}: status={status} goal={goal}".strip()
            kind = MemoryKind.MISSION_HISTORY
            if "fail" in event_type or status.lower() in {"failed", "cancelled"}:
                kind = MemoryKind.FAILURE_HISTORY
            await runtime.put(
                MemoryWrite(
                    kind=kind,
                    content=content,
                    title=f"Mission {mission_id or 'unknown'}",
                    importance=0.65,
                    tags=["mission", event_type.split(".")[-1]],
                    mission_id=mission_id or None,
                    source="event",
                )
            )
            if goal:
                await runtime.observe(
                    WorldObservation(
                        text=goal,
                        entities=[],
                        source="mission",
                        mission_id=mission_id or None,
                        confidence=0.6,
                    )
                )

        async def on_agent(event_type: str, payload: Mapping[str, Any]) -> None:
            agent_id = str(payload.get("agent_id") or "")
            kind_name = str(payload.get("kind") or "custom")
            title = str(payload.get("title") or event_type)
            await runtime.put(
                MemoryWrite(
                    kind=MemoryKind.EXECUTION_HISTORY,
                    content=f"Agent {kind_name} {event_type}: {title}",
                    title=f"Agent {agent_id}",
                    importance=0.55,
                    tags=["agent", kind_name, event_type.split(".")[-1]],
                    agent_id=agent_id or None,
                    mission_id=str(payload.get("mission_id") or "") or None,
                    source="event",
                )
            )
            if kind_name:
                await runtime.observe(
                    WorldObservation(
                        text=f"Agent {kind_name} completed work",
                        entities=[kind_name.title() + "Agent"],
                        relations=[
                            ObservedRelation(
                                subject=kind_name.title() + "Agent",
                                predicate="performed",
                                object=title[:48] or "task",
                            )
                        ],
                        source="agent",
                        confidence=0.55,
                    )
                )

        ctx.event_bus.subscribe("mission.*", on_mission)
        ctx.event_bus.subscribe("agent.completed", on_agent)
        ctx.event_bus.subscribe("agent.failed", on_agent)
