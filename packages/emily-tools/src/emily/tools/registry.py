"""Tool registry."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from emily.tools.errors import ToolNotFoundError
from emily.tools.models import ToolSource, ToolSpec

ToolHandler = Callable[[Mapping[str, Any]], Awaitable[Mapping[str, Any]]]


class RegisteredTool:
    def __init__(self, spec: ToolSpec, handler: ToolHandler) -> None:
        self.spec = spec
        self.handler = handler


class ToolRegistry:
    """In-process catalog of invocable tools."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        self._tools[spec.name] = RegisteredTool(spec=spec, handler=handler)

    def unregister(self, name: str) -> bool:
        return self._tools.pop(name, None) is not None

    def get(self, name: str) -> RegisteredTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(name) from exc

    def list_tools(
        self,
        *,
        source: ToolSource | None = None,
        include_disabled: bool = False,
    ) -> list[ToolSpec]:
        specs = [t.spec for t in self._tools.values()]
        if source is not None:
            specs = [s for s in specs if s.source == source]
        if not include_disabled:
            specs = [s for s in specs if s.enabled]
        return sorted(specs, key=lambda s: s.name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def clear_source(self, source: ToolSource) -> int:
        to_remove = [name for name, tool in self._tools.items() if tool.spec.source == source]
        for name in to_remove:
            del self._tools[name]
        return len(to_remove)
