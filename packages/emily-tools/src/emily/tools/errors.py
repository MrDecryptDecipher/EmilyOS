"""Tool runtime errors."""

from __future__ import annotations

from typing import Any

from emily.core.errors import EmilyError, ErrorCode


class ToolError(EmilyError):
    def __init__(
        self,
        message: str,
        *,
        tool_name: str | None = None,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged = {**(details or {})}
        if tool_name is not None:
            merged["tool_name"] = tool_name
        super().__init__(message, code=ErrorCode.TOOL_ERROR, details=merged, cause=cause)
        self.tool_name = tool_name


class ToolNotFoundError(ToolError):
    def __init__(self, tool_name: str) -> None:
        super().__init__(f"tool not found: {tool_name}", tool_name=tool_name)
        self.code = ErrorCode.NOT_FOUND


class ToolPermissionError(ToolError):
    def __init__(self, message: str, *, tool_name: str | None = None) -> None:
        super().__init__(message, tool_name=tool_name)
        self.code = ErrorCode.PERMISSION_DENIED


class ToolPolicyError(ToolError):
    def __init__(self, message: str, *, tool_name: str | None = None) -> None:
        super().__init__(message, tool_name=tool_name)
        self.code = ErrorCode.POLICY_DENIED
