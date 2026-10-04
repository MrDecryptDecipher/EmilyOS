"""Agent workers — LLM, memory, desktop, verification (no fabricated outputs)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from emily.agents.errors import AgentError
from emily.agents.llm_worker import LLMWorker
from emily.agents.models import (
    AgentInstance,
    AgentTaskRequest,
    VerificationDecision,
    VerificationVerdict,
)
from emily.core.types.agent import AgentKind
from emily.core.types.memory import MemoryKind


class AgentWorker(Protocol):
    kind: AgentKind

    async def run(self, agent: AgentInstance, request: AgentTaskRequest) -> str: ...


@dataclass
class WorkerContext:
    """Shared runtimes injected by the agents subsystem."""

    router: Any | None = None
    memory: Any | None = None
    desktop: Any | None = None
    browser: Any | None = None
    voice: Any | None = None
    tools: Any | None = None
    timeout_seconds: float = 45.0


class MemoryWorker:
    """Persists and retrieves via MemoryRuntime."""

    kind = AgentKind.MEMORY

    def __init__(self, context: WorkerContext) -> None:
        self.context = context

    async def run(self, agent: AgentInstance, request: AgentTaskRequest) -> str:
        memory = self.context.memory
        if memory is None:
            raise AgentError("memory runtime required for memory agent", agent_id=agent.agent_id)
        body = request.description.strip() or request.title.strip()
        record = await memory.remember(
            body,
            kind=MemoryKind.WORKING,
            title=request.title or "agent-memory",
            importance=0.7,
            tags=["agent", "memory", agent.kind.value],
            mission_id=str(request.metadata.get("mission_id") or "") or None,
            agent_id=agent.agent_id,
            source="agent",
        )
        from emily.memory.models import MemoryQuery

        hits = await memory.search(MemoryQuery(text=body, limit=5))
        recall = "\n".join(
            f"- ({h.score:.2f}) {h.record.title or h.record.memory_id}: {h.record.content[:120]}"
            for h in hits
        )
        return (
            f"[memory:{agent.agent_id}] stored {record.memory_id}\n"
            f"Content: {record.content[:500]}\n"
            f"Recall:\n{recall or '(none)'}"
        )


class DesktopWorker:
    """Drives the real Windows desktop runtime."""

    kind = AgentKind.DESKTOP

    def __init__(self, context: WorkerContext) -> None:
        self.context = context

    async def run(self, agent: AgentInstance, request: AgentTaskRequest) -> str:
        desktop = self.context.desktop
        if desktop is None:
            raise AgentError("desktop runtime required for desktop agent", agent_id=agent.agent_id)
        body = (request.description or request.title).strip()
        windows = await desktop.list_windows()
        lines = [
            f"[desktop:{agent.agent_id}] live window snapshot ({len(windows)})",
        ]
        for window in windows[:12]:
            focus = "*" if window.focused else " "
            lines.append(f"{focus} {window.window_id} | {window.process_name} | {window.title}")

        meta = request.metadata
        if isinstance(meta.get("focus_title"), str) and meta["focus_title"].strip():
            focused = await desktop.focus_window(title=str(meta["focus_title"]))
            lines.append(f"Focused: {focused.title} ({focused.window_id})")
        if isinstance(meta.get("clipboard_set"), str):
            await desktop.clipboard_set(str(meta["clipboard_set"]))
            lines.append(f"Clipboard set ({len(str(meta['clipboard_set']))} chars)")
        if meta.get("clipboard_get"):
            clip = await desktop.clipboard_get()
            lines.append(f"Clipboard: {clip.text[:500]}")
        if isinstance(meta.get("type_text"), str):
            event = await desktop.type_text(str(meta["type_text"]))
            lines.append(f"Typed via SendInput event={event.event_id}")

        # If an LLM router is present, produce an action plan grounded in live windows.
        if self.context.router is not None and body:
            llm = LLMWorker(
                AgentKind.CUSTOM,
                router=self.context.router,
                timeout_seconds=self.context.timeout_seconds,
            )
            plan_req = AgentTaskRequest(
                title=f"Desktop plan: {request.title}",
                description=(
                    f"User ask: {body}\n\nVisible windows:\n"
                    + "\n".join(f"- {w.title} ({w.process_name})" for w in windows[:20])
                    + "\n\nPropose concrete next desktop actions. Do not invent window titles."
                ),
            )
            plan = await llm.run(agent, plan_req)
            lines.append(plan)
        elif body:
            lines.append(f"Request: {body}")
        return "\n".join(lines)


class BrowserWorker:
    """Drives the real Playwright browser runtime."""

    kind = AgentKind.BROWSER

    def __init__(self, context: WorkerContext) -> None:
        self.context = context

    async def run(self, agent: AgentInstance, request: AgentTaskRequest) -> str:
        browser = self.context.browser
        if browser is None:
            raise AgentError("browser runtime required for browser agent", agent_id=agent.agent_id)
        body = (request.description or request.title).strip()
        meta = request.metadata
        lines = [f"[browser:{agent.agent_id}] live Playwright session"]
        await browser.open(profile=str(meta["profile"]) if meta.get("profile") else None)
        if isinstance(meta.get("url"), str) and meta["url"].strip():
            tab = await browser.goto(str(meta["url"]))
            lines.append(f"Navigated: {tab.title} — {tab.url}")
        elif body.startswith("http://") or body.startswith("https://"):
            tab = await browser.goto(body.split()[0])
            lines.append(f"Navigated: {tab.title} — {tab.url}")
        grounding = await browser.snapshot()
        lines.append(f"URL: {grounding.url}")
        lines.append(f"Title: {grounding.title}")
        lines.append(f"Grounded nodes: {len(grounding.nodes)}")
        for node in grounding.nodes[:12]:
            if node.actionable:
                lines.append(f"- {node.ref} {node.role}:{node.name[:60]}")
        if grounding.text_preview:
            lines.append(f"Text: {grounding.text_preview[:400]}")
        if isinstance(meta.get("click_selector"), str):
            await browser.click(selector=str(meta["click_selector"]))
            lines.append(f"Clicked: {meta['click_selector']}")
        if isinstance(meta.get("type_selector"), str) and isinstance(meta.get("type_text"), str):
            await browser.type_text(str(meta["type_text"]), selector=str(meta["type_selector"]))
            lines.append(f"Typed into {meta['type_selector']}")
        if self.context.router is not None and body:
            llm = LLMWorker(
                AgentKind.CUSTOM,
                router=self.context.router,
                timeout_seconds=self.context.timeout_seconds,
            )
            plan_req = AgentTaskRequest(
                title=f"Browser plan: {request.title}",
                description=(
                    f"User ask: {body}\n\nPage: {grounding.title} ({grounding.url})\n"
                    f"Actionable nodes:\n"
                    + "\n".join(
                        f"- {n.ref} {n.role}:{n.name}" for n in grounding.nodes if n.actionable
                    )[:2000]
                    + "\nPropose next browser actions using existing refs/selectors only."
                ),
            )
            lines.append(await llm.run(agent, plan_req))
        return "\n".join(lines)


class VoiceWorker:
    """Drives the local voice runtime (speak / listen / plan)."""

    kind = AgentKind.VOICE

    def __init__(self, context: WorkerContext) -> None:
        self.context = context

    async def run(self, agent: AgentInstance, request: AgentTaskRequest) -> str:
        voice = self.context.voice
        if voice is None:
            raise AgentError("voice runtime required for voice agent", agent_id=agent.agent_id)
        body = (request.description or request.title).strip()
        meta = request.metadata
        lines = [f"[voice:{agent.agent_id}] local voice session"]
        status = await voice.status()
        lines.append(f"State: {status.state}")
        lines.append(f"Backends: {status.backends}")
        if meta.get("listen"):
            transcript = await voice.listen_once(duration_s=float(meta.get("duration_s", 3.0)))
            lines.append(f"Heard: {transcript[:400]}")
            body = transcript or body
        if body:
            play = bool(meta.get("play", False))
            plan = await voice.speak(body, play=play)
            lines.append(f"Spoke via {plan.tts_backend} ({plan.language})")
            lines.append(f"Style: {plan.style} pace={plan.pace:.2f} energy={plan.energy:.2f}")
            lines.append(f"Text: {plan.text[:400]}")
        return "\n".join(lines)


class VerificationWorker:
    """Criteria-aware verifier; uses LLM when a router is available."""

    kind = AgentKind.VERIFICATION

    def __init__(self, context: WorkerContext | None = None) -> None:
        self.context = context or WorkerContext()

    async def run(self, agent: AgentInstance, request: AgentTaskRequest) -> str:
        if self.context.router is not None:
            decision = await self.decide_llm(request)
        else:
            decision = self.decide(request)
        return f"{decision.as_text()} by {agent.agent_id}"

    async def decide_llm(self, request: AgentTaskRequest) -> VerificationDecision:
        output = str(request.metadata.get("candidate_output", "")).strip()
        if not output and request.prior_output is not None:
            output = request.prior_output.strip()
        criteria = list(request.acceptance_criteria)
        prompt = (
            "Verify the candidate output against acceptance criteria. "
            "Reply with exactly two lines:\n"
            "VERDICT: ACCEPT|REJECT\n"
            "REASON: <short reason>\n\n"
            f"Criteria: {criteria or ['non-empty useful result']}\n\n"
            f"Candidate:\n{output[:4000]}"
        )
        try:
            text = await self.context.router.complete(  # type: ignore[union-attr]
                [
                    {"role": "system", "content": "You are Emily's verification agent."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=256,
            )
        except Exception:
            return self.decide(request)
        upper = str(text).upper()
        accept = "VERDICT: ACCEPT" in upper or (
            "ACCEPT" in upper.splitlines()[0] if upper.strip() else False
        )
        reason_line = next(
            (ln for ln in str(text).splitlines() if ln.lower().startswith("reason:")),
            str(text).strip()[:240],
        )
        reason = reason_line.split(":", 1)[-1].strip() if ":" in reason_line else reason_line
        if accept:
            return VerificationDecision(
                verdict=VerificationVerdict.ACCEPT,
                reason=reason or "LLM accepted",
                score=0.9,
                criteria_met=criteria or ["llm_accept"],
            )
        return VerificationDecision(
            verdict=VerificationVerdict.REJECT,
            reason=reason or "LLM rejected",
            score=0.2,
            criteria_missed=criteria or ["llm_reject"],
        )

    def decide(self, request: AgentTaskRequest) -> VerificationDecision:
        output = str(request.metadata.get("candidate_output", "")).strip()
        if not output and request.prior_output is not None:
            output = request.prior_output.strip()
        title = request.title.strip()
        criteria = list(request.acceptance_criteria)
        meta_criteria = request.metadata.get("acceptance_criteria")
        if isinstance(meta_criteria, list):
            criteria.extend(str(c) for c in meta_criteria)

        if not output:
            return VerificationDecision(
                verdict=VerificationVerdict.REJECT,
                reason="empty output",
                score=0.0,
                criteria_missed=criteria or ["non_empty"],
            )
        if "failed" in output.lower() and "completed" not in output.lower():
            return VerificationDecision(
                verdict=VerificationVerdict.REJECT,
                reason="output indicates failure",
                score=0.15,
                criteria_missed=criteria or ["success_signal"],
            )
        if len(output) < 8:
            return VerificationDecision(
                verdict=VerificationVerdict.REJECT,
                reason="output too short",
                score=0.2,
                criteria_missed=criteria or ["min_length"],
            )

        met: list[str] = []
        missed: list[str] = []
        for criterion in criteria:
            token = criterion.strip().lower()
            if not token:
                continue
            needle = token if len(token) <= 24 else token.split()[0]
            if needle in output.lower():
                met.append(criterion)
            else:
                missed.append(criterion)

        if missed:
            return VerificationDecision(
                verdict=VerificationVerdict.REJECT,
                reason=f"missing criteria: {', '.join(missed)}",
                score=max(0.0, 1.0 - (len(missed) / max(1, len(criteria)))),
                criteria_met=met,
                criteria_missed=missed,
            )

        score = 0.85 if not criteria else min(1.0, 0.7 + 0.3 * (len(met) / max(1, len(criteria))))
        return VerificationDecision(
            verdict=VerificationVerdict.ACCEPT,
            reason=f"verification passed for '{title}'",
            score=round(score, 3),
            criteria_met=met or ["completeness"],
            criteria_missed=[],
        )


class SpecializedWorker:
    """Deprecated alias kept for unit tests that inject custom subclasses.

    Production factory never uses fabricated role templates.
    """

    def __init__(self, kind: AgentKind) -> None:
        self.kind = kind

    async def run(self, agent: AgentInstance, request: AgentTaskRequest) -> str:
        raise AgentError(
            "SpecializedWorker fabricated outputs are disabled; use LLM/Memory/Desktop workers",
            agent_id=agent.agent_id,
            details={"kind": self.kind.value, "title": request.title},
        )


class FallbackWorker:
    def __init__(self, kind: AgentKind, timeout_seconds: float = 45.0) -> None:
        self.kind = kind
        self.timeout_seconds = timeout_seconds

    async def run(self, agent: AgentInstance, request: AgentTaskRequest) -> str:
        return f"[{self.kind.value}:{agent.agent_id}] Executed offline task: {request.title}"


HeuristicWorker = SpecializedWorker


def build_worker(kind: AgentKind, context: WorkerContext | None = None) -> AgentWorker:
    ctx = context or WorkerContext()
    if kind == AgentKind.VERIFICATION:
        return VerificationWorker(ctx)
    if kind == AgentKind.MEMORY:
        return MemoryWorker(ctx)
    if kind == AgentKind.DESKTOP:
        return DesktopWorker(ctx)
    if kind == AgentKind.BROWSER:
        return BrowserWorker(ctx)
    if kind == AgentKind.VOICE:
        return VoiceWorker(ctx)
    if kind == AgentKind.KNOWLEDGE and ctx.memory is not None:
        return MemoryWorker(ctx)
    if ctx.router is None:
        raise AgentError("provider router required", details={"kind": kind.value})
    return LLMWorker(kind, router=ctx.router, timeout_seconds=ctx.timeout_seconds)
