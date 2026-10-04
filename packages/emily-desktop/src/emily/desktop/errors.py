"""Desktop runtime errors."""

from __future__ import annotations

from typing import Any

from emily.core.errors import EmilyError, ErrorCode


class DesktopError(EmilyError):
    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, code=ErrorCode.TOOL_ERROR, details=details, cause=cause)


class DesktopPolicyError(DesktopError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details=details)
        self.code = ErrorCode.POLICY_DENIED


class DesktopNotFoundError(DesktopError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.code = ErrorCode.NOT_FOUND
