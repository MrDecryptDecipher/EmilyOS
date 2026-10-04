"""Worker factory with pluggable builders."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from emily.agents.workers import AgentWorker, WorkerContext, build_worker
from emily.core.types.agent import AgentKind

WorkerBuilder = Callable[[AgentKind], AgentWorker]


class WorkerFactory:
    """Creates real workers for agent kinds (LLM / memory / desktop)."""

    def __init__(
        self,
        *,
        use_llm: bool = True,
        router: Any | None = None,
        timeout_seconds: float = 45.0,
        memory: Any | None = None,
        desktop: Any | None = None,
        browser: Any | None = None,
        voice: Any | None = None,
        tools: Any | None = None,
    ) -> None:
        self.use_llm = use_llm
        self.router = router
        self.timeout_seconds = timeout_seconds
        self.memory = memory
        self.desktop = desktop
        self.browser = browser
        self.voice = voice
        self.tools = tools
        self._overrides: dict[AgentKind, WorkerBuilder] = {}

    def register(self, kind: AgentKind, builder: WorkerBuilder) -> None:
        self._overrides[kind] = builder

    def context(self) -> WorkerContext:
        return WorkerContext(
            router=self.router if self.use_llm else None,
            memory=self.memory,
            desktop=self.desktop,
            browser=self.browser,
            voice=self.voice,
            tools=self.tools,
            timeout_seconds=self.timeout_seconds,
        )

    def create(self, kind: AgentKind) -> AgentWorker:
        if kind in self._overrides:
            return self._overrides[kind](kind)
        return build_worker(kind, self.context())
