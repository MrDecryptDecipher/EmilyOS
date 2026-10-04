"""Memory & world-model errors."""

from __future__ import annotations

from typing import Any

from emily.core.errors import EmilyError, ErrorCode


class MemoryError(EmilyError):
    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, code=ErrorCode.INTERNAL, details=details, cause=cause)


class MemoryNotFoundError(MemoryError):
    def __init__(self, memory_id: str) -> None:
        super().__init__(f"memory not found: {memory_id}", details={"memory_id": memory_id})
        self.code = ErrorCode.NOT_FOUND
        self.memory_id = memory_id


class WorldError(MemoryError):
    """World-model specific failures."""
