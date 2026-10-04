"""LangGraph mission execution graph."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from emily.core.types.mission import MissionStatus
from emily.missions.control import ControlPlane
from emily.missions.executor_port import TaskExecutorSlot
from emily.missions.models import ControlSignal, Mission, TaskStatus
from emily.missions.planner import HeuristicPlanner, MissionPlanner


def _merge_dict(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    merged.update(right)
    return merged


class GraphState(TypedDict, total=False):
    mission_id: str
    goal: str
    status: str
    control: str
    entry: str
    objectives: list[dict[str, Any]]
    current_task_index: int
    verification: str
    reflection: str
    error: str
    events: Annotated[list[str], lambda left, right: [*left, *right]]
    extras: Annotated[dict[str, Any], _merge_dict]


class MissionGraphFactory:
    """Builds a compiled LangGraph for mission lifecycle.

    LangGraph thread state uses MemorySaver for async compatibility; durable
    mission archives are persisted by ``MissionStore``.
    """

    def __init__(
        self,
        planner: MissionPlanner | None = None,
        control_plane: ControlPlane | None = None,
        executor_slot: TaskExecutorSlot | None = None,
        *,
        checkpoint_path: Path | str | None = None,
    ) -> None:
        self.planner = planner or HeuristicPlanner()
        self.control_plane = control_plane or ControlPlane()
        self.executor_slot = executor_slot or TaskExecutorSlot()
        _ = checkpoint_path  # reserved for AsyncSqliteSaver wiring
        self.checkpointer = MemorySaver()

    def compile(self) -> Any:
        graph: StateGraph[GraphState] = StateGraph(GraphState)
        graph.add_node("plan", self._plan)
        graph.add_node("execute", self._execute)
        graph.add_node("verify", self._verify)
        graph.add_node("reflect", self._reflect)
        graph.add_node("finalize", self._finalize)

        graph.add_conditional_edges(
            START,
            self._route_entry,
            {"plan": "plan", "execute": "execute"},
        )
        graph.add_conditional_edges(
            "plan",
            self._after_plan,
            {"execute": "execute", "finalize": "finalize"},
        )
        graph.add_conditional_edges(
            "execute",
            self._after_execute,
            {"execute": "execute", "verify": "verify", "finalize": "finalize"},
        )
        graph.add_conditional_edges(
            "verify",
            self._after_verify,
            {"reflect": "reflect", "finalize": "finalize"},
        )
        graph.add_edge("reflect", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile(checkpointer=self.checkpointer)

    def _signal(self, state: GraphState) -> ControlSignal:
        mission_id = state.get("mission_id", "")
        live = self.control_plane.get(mission_id)
        if live != ControlSignal.RUN:
            return live
        raw = state.get("control", ControlSignal.RUN.value)
        try:
            return ControlSignal(raw)
        except ValueError:
            return ControlSignal.RUN

    def _route_entry(self, state: GraphState) -> Literal["plan", "execute"]:
        if state.get("entry") == "execute":
            return "execute"
        return "plan"

    async def _plan(self, state: GraphState) -> dict[str, Any]:
        signal = self._signal(state)
        if signal == ControlSignal.CANCEL:
            return {"status": MissionStatus.CANCELLED.value, "events": ["plan:cancelled"]}
        if signal == ControlSignal.PAUSE:
            return {"status": MissionStatus.PAUSED.value, "events": ["plan:paused"]}

        mission = Mission(mission_id=state["mission_id"], goal=state["goal"])
        planned = await self.planner.plan(mission)
        return {
            "status": MissionStatus.PLANNED.value,
            "control": ControlSignal.RUN.value,
            "objectives": [obj.model_dump(mode="json") for obj in planned.objectives],
            "current_task_index": 0,
            "events": ["plan:completed"],
        }

    async def _execute(self, state: GraphState) -> dict[str, Any]:
        signal = self._signal(state)
        if signal == ControlSignal.CANCEL:
            return {"status": MissionStatus.CANCELLED.value, "events": ["execute:cancelled"]}
        if signal == ControlSignal.PAUSE:
            return {"status": MissionStatus.PAUSED.value, "events": ["execute:paused"]}

        objectives = [dict(obj) for obj in state.get("objectives", [])]
        tasks: list[dict[str, Any]] = []
        for objective in objectives:
            tasks.extend(list(objective.get("tasks", [])))

        index = int(state.get("current_task_index", 0))
        if index >= len(tasks):
            return {"status": MissionStatus.VERIFYING.value, "events": ["execute:all_done"]}

        task = dict(tasks[index])
        executor = self.executor_slot.executor
        if executor is None:
            task["status"] = TaskStatus.FAILED.value
            task["error"] = "no task executor attached (agents subsystem required)"
            task["result"] = None
        else:
            task = await executor.execute_task(
                mission_id=str(state.get("mission_id", "")),
                task=task,
            )

        if task.get("status") == TaskStatus.FAILED.value:
            cursor = 0
            for objective in objectives:
                obj_tasks = list(objective.get("tasks", []))
                for t_index, _existing in enumerate(obj_tasks):
                    if cursor == index:
                        obj_tasks[t_index] = task
                    cursor += 1
                objective["tasks"] = obj_tasks
            return {
                "status": MissionStatus.FAILED.value,
                "objectives": objectives,
                "current_task_index": index,
                "error": str(task.get("error") or "task failed"),
                "events": [f"execute:task_failed:{task.get('task_id')}"],
            }

        cursor = 0
        for objective in objectives:
            obj_tasks = list(objective.get("tasks", []))
            for t_index, _existing in enumerate(obj_tasks):
                if cursor == index:
                    obj_tasks[t_index] = task
                cursor += 1
            objective["tasks"] = obj_tasks

        next_index = index + 1
        if next_index < len(tasks):
            cursor = 0
            for objective in objectives:
                obj_tasks = list(objective.get("tasks", []))
                for t_index, pending in enumerate(obj_tasks):
                    if cursor == next_index:
                        pending = dict(pending)
                        pending["status"] = TaskStatus.READY.value
                        obj_tasks[t_index] = pending
                    cursor += 1
                objective["tasks"] = obj_tasks

        return {
            "status": MissionStatus.RUNNING.value,
            "objectives": objectives,
            "current_task_index": next_index,
            "events": [f"execute:task:{task.get('task_id')}"],
        }

    async def _verify(self, state: GraphState) -> dict[str, Any]:
        signal = self._signal(state)
        if signal == ControlSignal.CANCEL:
            return {"status": MissionStatus.CANCELLED.value, "events": ["verify:cancelled"]}
        if signal == ControlSignal.PAUSE:
            return {"status": MissionStatus.PAUSED.value, "events": ["verify:paused"]}

        tasks: list[dict[str, Any]] = []
        for objective in state.get("objectives", []):
            tasks.extend(list(objective.get("tasks", [])))
        failed = [t for t in tasks if t.get("status") == TaskStatus.FAILED.value]
        if failed:
            return {
                "status": MissionStatus.FAILED.value,
                "verification": f"{len(failed)} task(s) failed",
                "error": str(failed[0].get("error") or "task failed"),
                "events": ["verify:failed"],
            }
        incomplete = [
            t
            for t in tasks
            if t.get("status")
            not in {TaskStatus.SUCCEEDED.value, TaskStatus.SKIPPED.value}
        ]
        if incomplete:
            return {
                "status": MissionStatus.FAILED.value,
                "verification": f"{len(incomplete)} task(s) incomplete",
                "error": "verification found incomplete tasks",
                "events": ["verify:failed"],
            }
        return {
            "status": MissionStatus.VERIFYING.value,
            "verification": f"All {len(tasks)} task(s) succeeded",
            "events": ["verify:passed"],
        }

    async def _reflect(self, state: GraphState) -> dict[str, Any]:
        signal = self._signal(state)
        if signal == ControlSignal.CANCEL:
            return {"status": MissionStatus.CANCELLED.value, "events": ["reflect:cancelled"]}
        tasks: list[dict[str, Any]] = []
        for objective in state.get("objectives", []):
            tasks.extend(list(objective.get("tasks", [])))
        summaries = [
            f"- {t.get('title')}: {str(t.get('result') or '')[:160]}" for t in tasks[:12]
        ]
        reflection = (
            f"Mission '{state.get('goal', '')}' verification: {state.get('verification', '')}\n"
            + "\n".join(summaries)
        )
        return {"reflection": reflection, "events": ["reflect:completed"]}

    async def _finalize(self, state: GraphState) -> dict[str, Any]:
        status = state.get("status", MissionStatus.SUCCEEDED.value)
        if status == MissionStatus.CANCELLED.value:
            final = MissionStatus.CANCELLED.value
        elif status == MissionStatus.FAILED.value:
            final = MissionStatus.FAILED.value
        elif status == MissionStatus.PAUSED.value:
            final = MissionStatus.PAUSED.value
        else:
            final = MissionStatus.SUCCEEDED.value
        return {"status": final, "events": [f"finalize:{final}"]}

    def _after_plan(self, state: GraphState) -> Literal["execute", "finalize"]:
        if state.get("status") in {
            MissionStatus.CANCELLED.value,
            MissionStatus.PAUSED.value,
            MissionStatus.FAILED.value,
        }:
            return "finalize"
        return "execute"

    def _after_execute(self, state: GraphState) -> Literal["execute", "verify", "finalize"]:
        if state.get("status") in {
            MissionStatus.CANCELLED.value,
            MissionStatus.PAUSED.value,
            MissionStatus.FAILED.value,
        }:
            return "finalize"
        tasks: list[dict[str, Any]] = []
        for objective in state.get("objectives", []):
            tasks.extend(list(objective.get("tasks", [])))
        index = int(state.get("current_task_index", 0))
        if index < len(tasks):
            return "execute"
        return "verify"

    def _after_verify(self, state: GraphState) -> Literal["reflect", "finalize"]:
        if state.get("status") in {
            MissionStatus.CANCELLED.value,
            MissionStatus.PAUSED.value,
            MissionStatus.FAILED.value,
        }:
            return "finalize"
        return "reflect"
