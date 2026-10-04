"""Optional mission task executor port (filled by agent runtime in M3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class TaskExecutor(Protocol):
    async def execute_task(
        self,
        *,
        mission_id: str,
        task: dict[str, Any],
    ) -> dict[str, Any]: ...


@dataclass
class TaskExecutorSlot:
    """Mutable holder so agents can attach after the graph is compiled."""

    executor: TaskExecutor | None = None
