"""Voice runtime errors."""

from __future__ import annotations

from typing import Any

from emily.core.errors import EmilyError, ErrorCode


class VoiceError(EmilyError):
    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
        code: ErrorCode = ErrorCode.TOOL_ERROR,
    ) -> None:
        super().__init__(message, code=code, details=details, cause=cause)


class VoicePolicyError(VoiceError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details=details, code=ErrorCode.POLICY_DENIED)


class ModelUnavailableError(VoiceError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details=details, code=ErrorCode.PROVIDER_UNAVAILABLE)


class BackendUnavailableError(VoiceError):
    def __init__(
        self,
        message: str,
        *,
        backend: str | None = None,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        payload = dict(details or {})
        if backend is not None:
            payload.setdefault("backend", backend)
        super().__init__(
            message,
            details=payload,
            cause=cause,
            code=ErrorCode.PROVIDER_UNAVAILABLE,
        )


class AudioError(VoiceError):
    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, details=details, cause=cause)


class ASRError(VoiceError):
    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, details=details, cause=cause)


class TTSError(VoiceError):
    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, details=details, cause=cause)


class VoiceInterruptedError(VoiceError):
    def __init__(self, message: str = "voice turn interrupted", *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details=details, code=ErrorCode.CANCELLED)
