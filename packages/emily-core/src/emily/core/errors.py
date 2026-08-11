"""Error taxonomy for Emily OS."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Stable machine-readable error codes."""

    INTERNAL = "emily.internal"
    VALIDATION = "emily.validation"
    CONFIG = "emily.config"
    NOT_FOUND = "emily.not_found"
    CONFLICT = "emily.conflict"
    TIMEOUT = "emily.timeout"
    CANCELLED = "emily.cancelled"
    PERMISSION_DENIED = "emily.permission_denied"
    POLICY_DENIED = "emily.policy_denied"
    PROVIDER_UNAVAILABLE = "emily.provider_unavailable"
    PROVIDER_ERROR = "emily.provider_error"
    TOOL_ERROR = "emily.tool_error"
    KERNEL_STATE = "emily.kernel_state"
    SUBSYSTEM = "emily.subsystem"
    EVENT_BUS = "emily.event_bus"


class EmilyError(Exception):
    """Base exception for all Emily OS failures."""

    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode = ErrorCode.INTERNAL,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details: dict[str, Any] = details or {}
        self.__cause__ = cause

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": str(self.code),
            "message": self.message,
            "details": self.details,
        }


class ConfigError(EmilyError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=ErrorCode.CONFIG, details=details)


class KernelStateError(EmilyError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=ErrorCode.KERNEL_STATE, details=details)


class EventBusError(EmilyError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=ErrorCode.EVENT_BUS, details=details)


class PermissionDeniedError(EmilyError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=ErrorCode.PERMISSION_DENIED, details=details)
