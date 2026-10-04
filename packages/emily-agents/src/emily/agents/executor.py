"""Mission task executor backed by the agent supervisor."""

from __future__ import annotations

from typing import Any

from emily.agents.models import AgentTaskRequest
from emily.agents.supervisor import AgentSupervisor
from emily.core.types.agent import AgentKind
from emily.missions.models import TaskStatus


class AgentTaskExecutor:
    """Adapts AgentSupervisor to the mission graph execute hook."""

    def __init__(self, supervisor: AgentSupervisor) -> None:
        self.supervisor = supervisor

    async def execute_task(
        self,
        *,
        mission_id: str,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        updated = dict(task)
        updated["status"] = TaskStatus.RUNNING.value
        metadata = dict(updated.get("metadata") or {})
        kind_raw = metadata.get("agent_kind")
        kind: AgentKind | None = None
        if isinstance(kind_raw, str):
            try:
                kind = AgentKind(kind_raw)
            except ValueError:
                kind = None

        criteria_raw = metadata.get("acceptance_criteria")
        criteria: list[str] = []
        if isinstance(criteria_raw, list):
            criteria = [str(c) for c in criteria_raw]

        max_retries = metadata.get("max_retries")
        retries = max_retries if isinstance(max_retries, int) else None

        request = AgentTaskRequest(
            title=str(updated.get("title") or updated.get("task_id") or "task"),
            description=str(updated.get("description") or ""),
            mission_id=mission_id,
            task_id=str(updated.get("task_id") or ""),
            kind=kind,
            max_retries=retries,
            acceptance_criteria=criteria,
            metadata=metadata,
        )
        result = await self.supervisor.run_task(request)
        if result.success:
            updated["status"] = TaskStatus.SUCCEEDED.value
            updated["result"] = result.output
            updated["error"] = None
        else:
            updated["status"] = TaskStatus.FAILED.value
            updated["result"] = result.output
            updated["error"] = result.error or result.verification or "agent failed"
        meta = dict(updated.get("metadata") or {})
        meta["agent_id"] = result.agent_id
        meta["agent_kind"] = result.kind.value
        meta["verification"] = result.verification
        meta["attempts"] = result.attempts
        meta["latency_ms"] = result.latency_ms
        meta["critique_trail"] = list(result.critique_trail)
        if result.decision is not None:
            meta["verification_score"] = result.decision.score
            meta["verification_verdict"] = result.decision.verdict.value
        updated["metadata"] = meta
        return updated
