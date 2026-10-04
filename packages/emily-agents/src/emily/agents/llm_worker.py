"""Optional provider-backed worker — real LLM calls, fail-closed."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from emily.agents.errors import AgentError
from emily.agents.models import AgentInstance, AgentTaskRequest
from emily.core.types.agent import AgentKind

logger = logging.getLogger(__name__)

_ROLE_PROMPTS: dict[AgentKind, str] = {
    AgentKind.RESEARCH: (
        "You are Emily's research agent. Produce findings with concrete claims, "
        "uncertainties, and citations when sources are known. Never invent URLs."
    ),
    AgentKind.CODING: (
        "You are Emily's coding agent. Produce an implementation plan and concrete "
        "code or diffs. Prefer correctness over verbosity."
    ),
    AgentKind.DOCUMENT: (
        "You are Emily's document agent. Draft clear, structured documents ready to publish."
    ),
    AgentKind.DATA: (
        "You are Emily's data agent. Analyze the request quantitatively when possible "
        "and state assumptions explicitly."
    ),
    AgentKind.AUTOMATION: (
        "You are Emily's automation agent. Produce an executable orchestration checklist "
        "with verification steps."
    ),
    AgentKind.SECURITY: (
        "You are Emily's security agent. Threat-model the request and recommend controls. "
        "Do not claim scans you did not run."
    ),
    AgentKind.MONITORING: (
        "You are Emily's monitoring agent. Diagnose health signals and propose alerts/metrics."
    ),
    AgentKind.KNOWLEDGE: (
        "You are Emily's knowledge agent. Produce reusable knowledge cards with links "
        "between concepts."
    ),
    AgentKind.CUSTOM: "You are an Emily specialist agent. Complete the task concretely.",
}


class LLMWorker:
    """Uses ProviderRouter.achat / complete — no heuristic/fake fallback."""

    def __init__(
        self,
        kind: AgentKind,
        *,
        router: Any | None = None,
        timeout_seconds: float = 45.0,
        model: str | None = None,
    ) -> None:
        self.kind = kind
        self.router = router
        self.timeout_seconds = timeout_seconds
        self.model = model

    async def run(self, agent: AgentInstance, request: AgentTaskRequest) -> str:
        if self.router is None:
            raise AgentError(
                "provider router required for LLM worker",
                agent_id=agent.agent_id,
            )
        system = _ROLE_PROMPTS.get(self.kind, _ROLE_PROMPTS[AgentKind.CUSTOM])
        user_parts = [
            f"Task: {request.title}",
            f"Details: {request.description or '(none)'}",
        ]
        if request.acceptance_criteria:
            user_parts.append(
                "Acceptance criteria:\n" + "\n".join(f"- {c}" for c in request.acceptance_criteria)
            )
        if request.prior_output:
            user_parts.append(f"Prior output:\n{request.prior_output[:2000]}")
        critique = str(request.metadata.get("critique", "")).strip()
        if critique:
            user_parts.append(f"Critique to incorporate:\n{critique}")
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]
        try:
            if hasattr(self.router, "complete"):
                text = await asyncio.wait_for(
                    self.router.complete(messages, max_tokens=1200),
                    timeout=self.timeout_seconds,
                )
            elif hasattr(self.router, "achat"):
                result = await asyncio.wait_for(
                    self.router.achat(messages, max_tokens=1200),
                    timeout=self.timeout_seconds,
                )
                text = _extract_text(result)
            else:
                raise AgentError(
                    "provider router missing complete/achat",
                    agent_id=agent.agent_id,
                )
        except AgentError:
            raise
        except Exception as exc:
            raise AgentError(
                f"LLM worker failed: {exc}",
                agent_id=agent.agent_id,
                cause=exc,
            ) from exc
        if not str(text).strip():
            raise AgentError("LLM worker returned empty content", agent_id=agent.agent_id)
        return f"[{self.kind.value}:{agent.agent_id}] {str(text).strip()}"


def _extract_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    for attr in ("content", "text", "output", "message"):
        value = getattr(result, attr, None)
        if isinstance(value, str):
            return value
    if isinstance(result, dict):
        for key in ("content", "text", "output", "message"):
            value = result.get(key)
            if isinstance(value, str):
                return value
    return str(result)
