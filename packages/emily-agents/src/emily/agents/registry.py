"""Built-in agent role registry with expanded kinds and inference."""

from __future__ import annotations

import re

from emily.agents.errors import AgentError
from emily.agents.models import AgentRoleSpec
from emily.core.types.agent import AgentKind

_BUILTIN: dict[AgentKind, AgentRoleSpec] = {
    AgentKind.RESEARCH: AgentRoleSpec(
        kind=AgentKind.RESEARCH,
        title="Research Agent",
        description="Gathers and synthesizes information for a task",
        capabilities=["research", "summarize", "cite", "compare"],
        default_max_retries=2,
        output_style="findings",
    ),
    AgentKind.CODING: AgentRoleSpec(
        kind=AgentKind.CODING,
        title="Coding Agent",
        description="Implements and refactors software changes",
        capabilities=["code", "diff", "review", "tests"],
        default_max_retries=2,
        output_style="diff",
    ),
    AgentKind.VERIFICATION: AgentRoleSpec(
        kind=AgentKind.VERIFICATION,
        title="Verification Agent",
        description="Validates outputs against task acceptance criteria",
        capabilities=["verify", "critique", "accept_reject", "score"],
        default_max_retries=0,
        output_style="verdict",
    ),
    AgentKind.DOCUMENT: AgentRoleSpec(
        kind=AgentKind.DOCUMENT,
        title="Document Agent",
        description="Drafts and edits documents",
        capabilities=["write", "edit", "format", "outline"],
        default_max_retries=1,
        output_style="document",
    ),
    AgentKind.DATA: AgentRoleSpec(
        kind=AgentKind.DATA,
        title="Data Agent",
        description="Analyzes structured data and produces insights",
        capabilities=["analyze", "transform", "report", "metrics"],
        default_max_retries=1,
        output_style="report",
    ),
    AgentKind.AUTOMATION: AgentRoleSpec(
        kind=AgentKind.AUTOMATION,
        title="Automation Agent",
        description="Coordinates multi-step operational workflows",
        capabilities=["orchestrate", "checklist", "handoff"],
        default_max_retries=1,
        output_style="checklist",
    ),
    AgentKind.SECURITY: AgentRoleSpec(
        kind=AgentKind.SECURITY,
        title="Security Agent",
        description="Threat modeling, policy checks, and secure review",
        capabilities=["threat_model", "policy", "audit"],
        default_max_retries=2,
        output_style="findings",
    ),
    AgentKind.MONITORING: AgentRoleSpec(
        kind=AgentKind.MONITORING,
        title="Monitoring Agent",
        description="Observability checks and health diagnostics",
        capabilities=["health", "alerts", "metrics"],
        default_max_retries=1,
        output_style="report",
    ),
    AgentKind.MEMORY: AgentRoleSpec(
        kind=AgentKind.MEMORY,
        title="Memory Agent",
        description="Stores and retrieves contextual knowledge via memory runtime",
        capabilities=["store", "recall", "summarize"],
        default_max_retries=1,
        output_style="memory",
    ),
    AgentKind.KNOWLEDGE: AgentRoleSpec(
        kind=AgentKind.KNOWLEDGE,
        title="Knowledge Agent",
        description="Organizes domain knowledge into reusable notes",
        capabilities=["index", "link", "explain"],
        default_max_retries=1,
        output_style="knowledge",
    ),
    AgentKind.DESKTOP: AgentRoleSpec(
        kind=AgentKind.DESKTOP,
        title="Desktop Agent",
        description="Controls Windows desktop via live Win32 desktop runtime",
        capabilities=["window", "input", "clipboard"],
        default_max_retries=1,
        output_style="actions",
    ),
    AgentKind.BROWSER: AgentRoleSpec(
        kind=AgentKind.BROWSER,
        title="Browser Agent",
        description="Controls browsers via Playwright + CDP runtime",
        capabilities=["navigate", "dom", "extract", "click", "type"],
        default_max_retries=1,
        output_style="actions",
    ),
    AgentKind.VOICE: AgentRoleSpec(
        kind=AgentKind.VOICE,
        title="Voice Agent",
        description="Local multilingual voice via Speech Director + TTS router",
        capabilities=["speak", "listen", "barge_in", "language"],
        default_max_retries=1,
        output_style="spoken",
    ),
    AgentKind.CUSTOM: AgentRoleSpec(
        kind=AgentKind.CUSTOM,
        title="Custom Agent",
        description="Generic worker for ad-hoc tasks",
        capabilities=["generic"],
        default_max_retries=1,
        output_style="generic",
    ),
}

_INFER_RULES: list[tuple[tuple[str, ...], AgentKind]] = [
    (("code", "implement", "refactor", "bug", "test", "patch", "compile"), AgentKind.CODING),
    (("research", "find", "investigate", "search", "survey"), AgentKind.RESEARCH),
    (("verify", "validate", "check", "qa", "accept", "reject"), AgentKind.VERIFICATION),
    (("doc", "write", "draft", "summary", "outline", "readme"), AgentKind.DOCUMENT),
    (("data", "analyze", "metric", "csv", "dataset", "chart"), AgentKind.DATA),
    (("security", "threat", "vuln", "cve", "policy", "auth"), AgentKind.SECURITY),
    (("monitor", "alert", "uptime", "latency", "slo"), AgentKind.MONITORING),
    (("memory", "recall", "remember", "forget"), AgentKind.MEMORY),
    (("knowledge", "wiki", "ontology", "catalog"), AgentKind.KNOWLEDGE),
    (("desktop", "window", "click", "clipboard", "uia"), AgentKind.DESKTOP),
    (("browser", "web page", "navigate", "playwright", "dom"), AgentKind.BROWSER),
    (("voice", "speak", "listen", "tts", "microphone", "barge"), AgentKind.VOICE),
]


class AgentRegistry:
    """Catalog of agent roles available for spawn."""

    def __init__(self, roles: dict[AgentKind, AgentRoleSpec] | None = None) -> None:
        self._roles = dict(roles or _BUILTIN)

    def get(self, kind: AgentKind) -> AgentRoleSpec:
        try:
            return self._roles[kind]
        except KeyError as exc:
            raise AgentError(f"unknown agent kind: {kind}") from exc

    def list_roles(self) -> list[AgentRoleSpec]:
        return [self._roles[k] for k in sorted(self._roles, key=lambda item: item.value)]

    def register(self, spec: AgentRoleSpec) -> None:
        self._roles[spec.kind] = spec

    def has(self, kind: AgentKind) -> bool:
        return kind in self._roles

    def infer_kind(self, title: str, description: str = "") -> AgentKind:
        text = f"{title} {description}".lower()
        words = set(re.findall(r"[a-z0-9_]+", text))
        for tokens, kind in _INFER_RULES:
            for token in tokens:
                if " " in token:
                    if token in text and kind in self._roles:
                        return kind
                elif token in words and kind in self._roles:
                    return kind
        return AgentKind.AUTOMATION if AgentKind.AUTOMATION in self._roles else AgentKind.CUSTOM
