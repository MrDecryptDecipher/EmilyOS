"""Mission runtime control plane."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from emily.core.types.mission import MissionStatus
from emily.missions.control import ControlPlane
from emily.missions.errors import MissionStateError
from emily.missions.executor_port import TaskExecutorSlot
from emily.missions.graph import MissionGraphFactory
from emily.missions.models import ControlSignal, Mission, MissionSpec, Objective
from emily.missions.planner import HeuristicPlanner, LLMPlanner, MissionPlanner
from emily.missions.store import MissionStore


class MissionRuntime:
    """Create, run, pause, resume, and cancel missions."""

    def __init__(
        self,
        store: MissionStore,
        *,
        planner: MissionPlanner | None = None,
        control_plane: ControlPlane | None = None,
        graph_factory: MissionGraphFactory | None = None,
        event_bus: Any | None = None,
        logger: Any | None = None,
    ) -> None:
        self.store = store
        self.control_plane = control_plane or ControlPlane()
        self.planner = planner or HeuristicPlanner()
        if graph_factory is not None:
            self.graph_factory = graph_factory
            self.executor_slot = graph_factory.executor_slot
        else:
            self.executor_slot = TaskExecutorSlot()
            self.graph_factory = MissionGraphFactory(
                planner=self.planner,
                control_plane=self.control_plane,
                executor_slot=self.executor_slot,
                checkpoint_path=Path(store.root) / "checkpoints.sqlite",
            )
        self.graph = self.graph_factory.compile()
        self.event_bus = event_bus
        self.logger = logger
        self._resume_generation: dict[str, int] = {}

    def set_task_executor(self, executor: object | None) -> None:
        self.executor_slot.executor = executor  # type: ignore[assignment]

    @classmethod
    def create_default(
        cls,
        *,
        missions_dir: Path | str = Path("data/missions"),
        provider_router: Any | None = None,
        use_llm_planner: bool = True,
        event_bus: Any | None = None,
        logger: Any | None = None,
        checkpoint_path: Path | str | None = None,
    ) -> MissionRuntime:
        planner: MissionPlanner
        if use_llm_planner and provider_router is not None:
            planner = LLMPlanner(router=provider_router)
        elif use_llm_planner and provider_router is None:
            planner = HeuristicPlanner()
        else:
            planner = HeuristicPlanner()
        control = ControlPlane()
        slot = TaskExecutorSlot()
        factory = MissionGraphFactory(
            planner=planner,
            control_plane=control,
            executor_slot=slot,
            checkpoint_path=checkpoint_path,
        )
        return cls(
            MissionStore(missions_dir),
            planner=planner,
            control_plane=control,
            graph_factory=factory,
            event_bus=event_bus,
            logger=logger,
        )

    async def create(self, spec: MissionSpec) -> Mission:
        mission = Mission(
            goal=spec.goal,
            priority=spec.priority,
            require_human_approval=spec.require_human_approval,
            metadata=dict(spec.metadata),
            status=MissionStatus.DRAFT,
        )
        self.control_plane.set(mission.mission_id, ControlSignal.RUN)
        await self.store.save(mission)
        await self._emit("mission.created", mission)
        return mission

    async def get(self, mission_id: str) -> Mission:
        return await self.store.get(mission_id)

    async def list(self) -> list[Mission]:
        return await self.store.list_missions()

    async def start(self, mission_id: str) -> Mission:
        mission = await self.store.get(mission_id)
        if mission.status == MissionStatus.CANCELLED:
            raise MissionStateError(
                "cannot start a cancelled mission",
                mission_id=mission_id,
            )
        if mission.status not in {
            MissionStatus.DRAFT,
            MissionStatus.PLANNED,
            MissionStatus.PAUSED,
            MissionStatus.FAILED,
        }:
            if mission.status == MissionStatus.SUCCEEDED:
                raise MissionStateError(
                    "mission already succeeded",
                    mission_id=mission_id,
                )
        self.control_plane.set(mission_id, ControlSignal.RUN)
        mission.control = ControlSignal.RUN
        mission.status = MissionStatus.RUNNING
        await self.store.save(mission)
        await self._emit("mission.started", mission)

        config = {"configurable": {"thread_id": mission_id}}
        result = await self.graph.ainvoke(
            {
                "mission_id": mission.mission_id,
                "goal": mission.goal,
                "status": mission.status.value,
                "control": ControlSignal.RUN.value,
                "entry": "plan",
                "objectives": [],
                "current_task_index": 0,
                "events": [],
                "extras": {},
            },
            config=config,
        )
        return await self._persist_graph_result(mission_id, result)

    async def pause(self, mission_id: str) -> Mission:
        self.control_plane.set(mission_id, ControlSignal.PAUSE)
        mission = await self.store.get(mission_id)
        mission.control = ControlSignal.PAUSE
        mission.status = MissionStatus.PAUSED
        await self.store.save(mission)
        await self._emit("mission.paused", mission)
        return mission

    async def cancel(self, mission_id: str) -> Mission:
        self.control_plane.set(mission_id, ControlSignal.CANCEL)
        mission = await self.store.get(mission_id)
        mission.control = ControlSignal.CANCEL
        mission.status = MissionStatus.CANCELLED
        await self.store.save(mission)
        await self._emit("mission.cancelled", mission)
        return mission

    async def resume(self, mission_id: str) -> Mission:
        mission = await self.store.get(mission_id)
        if mission.status not in {
            MissionStatus.PAUSED,
            MissionStatus.PLANNED,
            MissionStatus.RUNNING,
        }:
            raise MissionStateError(
                f"cannot resume mission in status {mission.status.value}",
                mission_id=mission_id,
            )
        self.control_plane.set(mission_id, ControlSignal.RUN)
        mission.control = ControlSignal.RUN
        mission.status = MissionStatus.RUNNING
        await self.store.save(mission)
        await self._emit("mission.resumed", mission)

        gen = self._resume_generation.get(mission_id, 0) + 1
        self._resume_generation[mission_id] = gen
        thread_id = f"{mission_id}:resume:{gen}"
        config = {"configurable": {"thread_id": thread_id}}
        result = await self.graph.ainvoke(
            {
                "mission_id": mission.mission_id,
                "goal": mission.goal,
                "status": MissionStatus.RUNNING.value,
                "control": ControlSignal.RUN.value,
                "entry": "execute" if mission.objectives else "plan",
                "objectives": [obj.model_dump(mode="json") for obj in mission.objectives],
                "current_task_index": int(mission.metadata.get("current_task_index", 0)),
                "events": [],
                "extras": {},
            },
            config=config,
        )
        return await self._persist_graph_result(mission_id, result)

    async def _persist_graph_result(self, mission_id: str, result: dict[str, Any]) -> Mission:
        mission = await self.store.get(mission_id)
        mission.status = MissionStatus(str(result.get("status", mission.status.value)))
        mission.verification = result.get("verification")
        mission.reflection = result.get("reflection")
        mission.error = result.get("error")
        if "objectives" in result:
            mission.objectives = [Objective.model_validate(obj) for obj in result["objectives"]]
        mission.metadata["current_task_index"] = int(result.get("current_task_index", 0))
        mission.metadata["events"] = list(result.get("events", []))
        mission.checkpoint_id = mission_id
        if mission.status == MissionStatus.PAUSED:
            mission.control = ControlSignal.PAUSE
        elif mission.status == MissionStatus.CANCELLED:
            mission.control = ControlSignal.CANCEL
        else:
            mission.control = ControlSignal.RUN
        await self.store.save(mission)
        await self._emit("mission.updated", mission)
        return mission

    async def _emit(self, event_type: str, mission: Mission) -> None:
        if self.event_bus is None:
            return
        await self.event_bus.publish(
            event_type,
            {
                "mission_id": mission.mission_id,
                "status": mission.status.value,
                "goal": mission.goal,
            },
            source="missions",
        )
