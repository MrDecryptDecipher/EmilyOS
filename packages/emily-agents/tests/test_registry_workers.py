"""Agent registry and worker tests."""

from __future__ import annotations

from typing import Any

import pytest

from emily.agents.errors import AgentError
from emily.agents.llm_worker import LLMWorker
from emily.agents.models import AgentInstance, AgentTaskRequest
from emily.agents.registry import AgentRegistry
from emily.agents.workers import VerificationWorker, WorkerContext, build_worker
from emily.core.types.agent import AgentKind, AgentStatus


class _ScriptedRouter:
    async def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        return f"completed: {messages[-1]['content'][:200]}"


def test_registry_infer_kind() -> None:
    registry = AgentRegistry()
    assert registry.infer_kind("Implement login bugfix") == AgentKind.CODING
    assert registry.infer_kind("Research market trends") == AgentKind.RESEARCH
    assert registry.infer_kind("Draft summary document") == AgentKind.DOCUMENT
    assert registry.infer_kind("Analyze CSV metrics") == AgentKind.DATA
    assert registry.infer_kind("Do the thing") == AgentKind.AUTOMATION


def test_registry_list_and_get() -> None:
    registry = AgentRegistry()
    roles = registry.list_roles()
    assert any(r.kind == AgentKind.VERIFICATION for r in roles)
    assert registry.get(AgentKind.CODING).title == "Coding Agent"
    assert len(roles) >= 10


@pytest.mark.asyncio
async def test_heuristic_and_verification_workers() -> None:
    with pytest.raises(AgentError, match="provider router required"):
        build_worker(AgentKind.RESEARCH)

    worker = build_worker(AgentKind.RESEARCH, WorkerContext(router=_ScriptedRouter()))
    assert isinstance(worker, LLMWorker)
    agent = AgentInstance(kind=AgentKind.RESEARCH, status=AgentStatus.RUNNING)
    output = await worker.run(
        agent,
        AgentTaskRequest(title="Research X", description="Find facts about X"),
    )
    assert "completed:" in output
    assert "Research X" in output

    verifier = VerificationWorker()
    accept = await verifier.run(
        AgentInstance(kind=AgentKind.VERIFICATION),
        AgentTaskRequest(
            title="Verify",
            metadata={"candidate_output": output},
        ),
    )
    assert accept.startswith("ACCEPT")
    reject = await verifier.run(
        AgentInstance(kind=AgentKind.VERIFICATION),
        AgentTaskRequest(title="Verify", metadata={"candidate_output": ""}),
    )
    assert reject.startswith("REJECT")
