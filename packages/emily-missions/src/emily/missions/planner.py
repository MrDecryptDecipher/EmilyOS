"""Mission planners — LLM-first with explicit heuristic only when requested."""

from __future__ import annotations

import asyncio
from typing import Protocol

from emily.missions.errors import MissionError
from emily.missions.models import Mission, Objective, Task, TaskStatus


class MissionPlanner(Protocol):
    async def plan(self, mission: Mission) -> Mission: ...


class HeuristicPlanner:
    """Deterministic structural planner used only when explicitly selected."""

    async def plan(self, mission: Mission) -> Mission:
        goal = mission.goal.strip()
        chunks = [part.strip() for part in goal.replace(";", ".").split(".") if part.strip()]
        if not chunks:
            chunks = [goal or "Complete requested work"]

        tasks = [
            Task(
                title=f"Step {index + 1}: {chunk[:80]}",
                description=chunk,
                status=TaskStatus.READY if index == 0 else TaskStatus.PENDING,
            )
            for index, chunk in enumerate(chunks[:8])
        ]
        for index in range(1, len(tasks)):
            tasks[index].depends_on = [tasks[index - 1].task_id]

        mission.objectives = [
            Objective(
                title="Primary objective",
                description=goal,
                tasks=tasks,
            )
        ]
        return mission


class LLMPlanner:
    """Provider-backed planner — fails closed (no silent fake plans)."""

    def __init__(self, router: object | None = None) -> None:
        self._router = router

    async def plan(self, mission: Mission) -> Mission:
        if self._router is None:
            raise MissionError("LLMPlanner requires a provider router")
        try:
            achat = getattr(self._router, "achat", None)
            if achat is None:
                raise MissionError("LLMPlanner router missing achat")
            result = await asyncio.wait_for(
                achat(
                    [
                        {
                            "role": "system",
                            "content": (
                                "Decompose the user goal into 3-6 short actionable tasks. "
                                "Return plain text, one task per line, no numbering. "
                                "Do not invent completed work."
                            ),
                        },
                        {"role": "user", "content": mission.goal},
                    ],
                    max_tokens=256,
                ),
                timeout=45.0,
            )
            lines = [
                line.strip("- ").strip()
                for line in str(result.content).splitlines()
                if line.strip()
            ]
            if not lines:
                raise MissionError("LLM planner returned no tasks")
            tasks = [
                Task(
                    title=line[:80],
                    description=line,
                    status=TaskStatus.READY if index == 0 else TaskStatus.PENDING,
                )
                for index, line in enumerate(lines[:8])
            ]
            for index in range(1, len(tasks)):
                tasks[index].depends_on = [tasks[index - 1].task_id]
            mission.objectives = [
                Objective(title="LLM planned objective", description=mission.goal, tasks=tasks)
            ]
            return mission
        except MissionError:
            raise
        except Exception as exc:
            raise MissionError(f"LLM planner failed: {exc}", cause=exc) from exc
