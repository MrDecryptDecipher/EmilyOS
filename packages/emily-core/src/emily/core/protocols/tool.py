"""Tool execution port (runtime in M5)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from emily.core.types.tool import ToolPermissionLevel


@runtime_checkable
class ToolPort(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    @property
    def permissions(self) -> frozenset[ToolPermissionLevel]: ...

    async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]: ...
