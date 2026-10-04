"""Human-in-the-loop approval gate manager for sensitive operations."""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from emily.core.ids import new_id


@dataclass
class ApprovalRequest:
    request_id: str
    action_type: str
    description: str
    details: dict[str, Any] = field(default_factory=dict)
    approved: bool | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class ApprovalGateManager:
    """Manages explicit human approval requests before executing high-risk operations."""

    def __init__(self, auto_approve_read: bool = True) -> None:
        self.auto_approve_read = auto_approve_read
        self._pending: dict[str, ApprovalRequest] = {}
        self._history: list[ApprovalRequest] = []

    def request_approval(self, action_type: str, description: str, details: dict[str, Any] | None = None) -> ApprovalRequest:
        """Create a pending approval request."""
        req_id = new_id("appr")
        req = ApprovalRequest(
            request_id=req_id,
            action_type=action_type,
            description=description,
            details=details or {},
        )
        self._pending[req_id] = req
        return req

    def respond(self, request_id: str, approved: bool) -> bool:
        """Record user response to approval request."""
        req = self._pending.pop(request_id, None)
        if not req:
            return False
        req.approved = approved
        self._history.append(req)
        return True

    def list_pending(self) -> list[ApprovalRequest]:
        """List current pending approval requests."""
        return list(self._pending.values())

    def list_history(self) -> list[ApprovalRequest]:
        """List historical resolved requests."""
        return list(self._history)
