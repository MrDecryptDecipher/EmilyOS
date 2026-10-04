"""Work + verification retry loop with critique feedback."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from emily.agents.models import (
    AgentInstance,
    AgentRunResult,
    AgentTaskRequest,
    VerificationDecision,
    VerificationVerdict,
)
from emily.agents.registry import AgentRegistry
from emily.agents.workers import AgentWorker, VerificationWorker, build_worker
from emily.core.types.agent import AgentKind, AgentStatus

StatusCallback = Callable[[AgentStatus], Awaitable[None]]
EventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class VerificationLoop:
    """Runs a work agent, then a verification agent, with capped critique retries."""

    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self.registry = registry or AgentRegistry()

    async def run(
        self,
        *,
        work_agent_id: str,
        work_kind: AgentKind,
        request: AgentTaskRequest,
        max_retries: int | None = None,
        work_worker: AgentWorker | None = None,
        verify_worker: AgentWorker | None = None,
        on_status: StatusCallback | None = None,
        on_event: EventCallback | None = None,
    ) -> AgentRunResult:
        role = self.registry.get(work_kind)
        retries = (
            request.max_retries
            if request.max_retries is not None
            else (role.default_max_retries if max_retries is None else max_retries)
        )
        worker = work_worker or build_worker(work_kind)
        verifier = verify_worker or build_worker(AgentKind.VERIFICATION)
        started = time.perf_counter()

        attempt = 0
        last_output = ""
        last_verification = ""
        last_decision: VerificationDecision | None = None
        critique_trail: list[str] = []
        working_request = request

        # When the work agent *is* the verifier, evaluate prior/candidate once (no nested verify).
        if work_kind == AgentKind.VERIFICATION and isinstance(worker, VerificationWorker):
            if on_status is not None:
                await on_status(AgentStatus.RUNNING)
            candidate = str(working_request.metadata.get("candidate_output", "")).strip()
            if not candidate:
                if working_request.prior_output is not None:
                    candidate = working_request.prior_output.strip()
                else:
                    candidate = (
                        working_request.description.strip() or working_request.title.strip()
                    )
            decide_req = working_request.model_copy(
                update={
                    "metadata": {
                        **working_request.metadata,
                        "candidate_output": candidate,
                    }
                }
            )
            last_decision = worker.decide(decide_req)
            last_output = last_decision.as_text()
            last_verification = last_output
            latency = round((time.perf_counter() - started) * 1000, 3)
            if on_event is not None:
                await on_event(
                    "agent.verified",
                    {
                        "agent_id": work_agent_id,
                        "kind": work_kind.value,
                        "attempt": 1,
                        "accepted": last_decision.accepted,
                        "verification": last_verification,
                    },
                )
            if last_decision.accepted:
                if on_status is not None:
                    await on_status(AgentStatus.IDLE)
                return AgentRunResult(
                    agent_id=work_agent_id,
                    kind=work_kind,
                    success=True,
                    output=last_output,
                    verification=last_verification,
                    decision=last_decision,
                    attempts=1,
                    latency_ms=latency,
                )
            if on_status is not None:
                await on_status(AgentStatus.FAILED)
            return AgentRunResult(
                agent_id=work_agent_id,
                kind=work_kind,
                success=False,
                output=last_output,
                verification=last_verification,
                decision=last_decision,
                attempts=1,
                latency_ms=latency,
                error=last_decision.reason,
            )

        while attempt <= retries:
            attempt += 1
            if on_status is not None:
                await on_status(AgentStatus.RUNNING)
            if on_event is not None and attempt > 1:
                await on_event(
                    "agent.retry",
                    {
                        "agent_id": work_agent_id,
                        "kind": work_kind.value,
                        "attempt": attempt,
                        "critique": critique_trail[-1] if critique_trail else "",
                    },
                )

            work_agent = AgentInstance(
                agent_id=work_agent_id,
                kind=work_kind,
                status=AgentStatus.RUNNING,
                mission_id=working_request.mission_id,
                task_id=working_request.task_id,
            )
            last_output = await worker.run(work_agent, working_request)

            verify_request = AgentTaskRequest(
                title=f"Verify: {working_request.title}",
                description=working_request.description,
                mission_id=working_request.mission_id,
                task_id=working_request.task_id,
                kind=AgentKind.VERIFICATION,
                acceptance_criteria=list(working_request.acceptance_criteria),
                metadata={
                    "candidate_output": last_output,
                    "acceptance_criteria": list(working_request.acceptance_criteria),
                },
            )
            verify_agent = AgentInstance(
                agent_id=f"verify_{work_agent_id}_{attempt}",
                kind=AgentKind.VERIFICATION,
                status=AgentStatus.RUNNING,
                mission_id=working_request.mission_id,
                task_id=working_request.task_id,
            )

            if isinstance(verifier, VerificationWorker):
                last_decision = verifier.decide(verify_request)
                last_verification = f"{last_decision.as_text()} by {verify_agent.agent_id}"
            else:
                last_verification = await verifier.run(verify_agent, verify_request)
                accepted = last_verification.upper().startswith("ACCEPT")
                last_decision = VerificationDecision(
                    verdict=VerificationVerdict.ACCEPT if accepted else VerificationVerdict.REJECT,
                    reason=last_verification,
                    score=1.0 if accepted else 0.0,
                )

            if on_event is not None:
                await on_event(
                    "agent.verified",
                    {
                        "agent_id": work_agent_id,
                        "kind": work_kind.value,
                        "attempt": attempt,
                        "accepted": last_decision.accepted,
                        "verification": last_verification,
                    },
                )

            if last_decision.accepted:
                if on_status is not None:
                    await on_status(AgentStatus.IDLE)
                return AgentRunResult(
                    agent_id=work_agent_id,
                    kind=work_kind,
                    success=True,
                    output=last_output,
                    verification=last_verification,
                    decision=last_decision,
                    attempts=attempt,
                    latency_ms=round((time.perf_counter() - started) * 1000, 3),
                    critique_trail=critique_trail,
                )

            critique = last_decision.reason
            critique_trail.append(critique)
            meta = dict(working_request.metadata)
            meta["critique"] = critique
            meta["attempt"] = attempt
            working_request = working_request.model_copy(
                update={
                    "metadata": meta,
                    "description": (
                        f"{request.description}\n\nAddress verification feedback: {critique}"
                    ).strip(),
                }
            )

        if on_status is not None:
            await on_status(AgentStatus.FAILED)
        return AgentRunResult(
            agent_id=work_agent_id,
            kind=work_kind,
            success=False,
            output=last_output,
            verification=last_verification,
            decision=last_decision,
            attempts=attempt,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            error="verification rejected after retries",
            critique_trail=critique_trail,
        )
