"""Provider-specific errors."""

from __future__ import annotations

from typing import Any

from emily.core.errors import EmilyError, ErrorCode


class ProviderInvocationError(EmilyError):
    def __init__(
        self,
        message: str,
        *,
        provider: str,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged = {"provider": provider, **(details or {})}
        super().__init__(
            message,
            code=ErrorCode.PROVIDER_ERROR,
            details=merged,
            cause=cause,
        )
        self.provider = provider


class ProviderUnavailableError(EmilyError):
    def __init__(
        self,
        message: str,
        *,
        provider: str,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged = {"provider": provider, **(details or {})}
        super().__init__(
            message,
            code=ErrorCode.PROVIDER_UNAVAILABLE,
            details=merged,
            cause=cause,
        )
        self.provider = provider
