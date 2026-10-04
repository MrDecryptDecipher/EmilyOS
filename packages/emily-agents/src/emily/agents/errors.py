"""Agent runtime errors."""

from __future__ import annotations

from typing import Any

from emily.core.errors import EmilyError, ErrorCode


class AgentError(EmilyError):
    def __init__(
        self,
        message: str,
        *,
        agent_id: str | None = None,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged = {**(details or {})}
        if agent_id is not None:
            merged["agent_id"] = agent_id
        super().__init__(message, code=ErrorCode.INTERNAL, details=merged, cause=cause)
        self.agent_id = agent_id


class AgentNotFoundError(AgentError):
    def __init__(self, agent_id: str) -> None:
        super().__init__(f"agent not found: {agent_id}", agent_id=agent_id)
        self.code = ErrorCode.NOT_FOUND


class AgentStateError(AgentError):
    def __init__(self, message: str, *, agent_id: str | None = None) -> None:
        super().__init__(message, agent_id=agent_id)
        self.code = ErrorCode.CONFLICT


class AgentCapacityError(AgentError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details=details)
        self.code = ErrorCode.PROVIDER_UNAVAILABLE
