"""Multi-agent pipeline and fan-out orchestration."""

from __future__ import annotations

import asyncio
from typing import Any

from emily.agents.models import AgentRunResult, AgentTaskRequest, PipelineResult, PipelineStep
from emily.agents.supervisor import AgentSupervisor
from emily.core.types.agent import AgentKind


class AgentTeam:
    """Coordinates sequential pipelines and concurrent fan-out runs."""

    def __init__(self, supervisor: AgentSupervisor) -> None:
        self.supervisor = supervisor

    async def run_pipeline(
        self,
        steps: list[PipelineStep],
        *,
        mission_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PipelineResult:
        if not steps:
            return PipelineResult(success=False, error="empty pipeline")

        results: list[AgentRunResult] = []
        prior: str | None = None
        for index, step in enumerate(steps):
            request = AgentTaskRequest(
                title=step.title,
                description=step.description,
                mission_id=mission_id,
                kind=step.kind,
                prior_output=prior if step.handoff else None,
                metadata={
                    **(metadata or {}),
                    "pipeline_index": index,
                    "pipeline_total": len(steps),
                },
            )
            result = await self.supervisor.run_task(request)
            results.append(result)
            if not result.success:
                return PipelineResult(
                    success=False,
                    steps=results,
                    final_output=result.output,
                    error=result.error or result.verification or f"step {index} failed",
                )
            prior = result.output

        return PipelineResult(
            success=True,
            steps=results,
            final_output=results[-1].output if results else "",
        )

    async def run_fanout(
        self,
        requests: list[AgentTaskRequest],
    ) -> list[AgentRunResult]:
        if not requests:
            return []
        return list(await asyncio.gather(*(self.supervisor.run_task(r) for r in requests)))

    async def run_goal_pipeline(
        self,
        goal: str,
        *,
        mission_id: str | None = None,
    ) -> PipelineResult:
        """Split a dotted/period goal into sequential agent steps with kind inference."""
        parts = [p.strip() for p in goal.replace("!", ".").split(".") if p.strip()]
        if not parts:
            parts = [goal.strip() or "Execute goal"]
        steps = [
            PipelineStep(
                title=part,
                description=part,
                kind=self.supervisor.registry.infer_kind(part),
            )
            for part in parts
        ]
        # Prefer ending with verification when the last step is not already verification.
        if steps[-1].kind != AgentKind.VERIFICATION and len(steps) > 1:
            steps.append(
                PipelineStep(
                    title=f"Verify: {goal}",
                    description="Confirm prior pipeline outputs satisfy the goal",
                    kind=AgentKind.VERIFICATION,
                    handoff=True,
                )
            )
        return await self.run_pipeline(steps, mission_id=mission_id)
