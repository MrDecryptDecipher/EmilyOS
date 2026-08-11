"""Policy engine port (security runtime in M9)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PolicyEnginePort(Protocol):
    async def authorize(
        self,
        *,
        principal: str,
        action: str,
        resource: str,
        context: Mapping[str, Any] | None = None,
    ) -> bool: ...
