"""Mission runtime errors."""

from __future__ import annotations

from typing import Any

from emily.core.errors import EmilyError, ErrorCode


class MissionError(EmilyError):
    def __init__(
        self,
        message: str,
        *,
        mission_id: str | None = None,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged = {**(details or {})}
        if mission_id is not None:
            merged["mission_id"] = mission_id
        super().__init__(message, code=ErrorCode.CONFLICT, details=merged, cause=cause)
        self.mission_id = mission_id


class MissionNotFoundError(MissionError):
    def __init__(self, mission_id: str) -> None:
        super().__init__(
            f"mission not found: {mission_id}",
            mission_id=mission_id,
        )
        self.code = ErrorCode.NOT_FOUND


class MissionStateError(MissionError):
    def __init__(self, message: str, *, mission_id: str | None = None) -> None:
        super().__init__(message, mission_id=mission_id)
        self.code = ErrorCode.KERNEL_STATE
