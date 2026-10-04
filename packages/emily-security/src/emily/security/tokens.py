"""Capability token validation and permission scoping engine."""

from datetime import UTC, datetime, timedelta
from typing import Any

from emily.core.ids import new_id
from emily.core.types.tool import ToolPermissionLevel
from emily.tools.models import CapabilityToken


class CapabilityTokenManager:
    """Issues and validates scoped capability tokens for agent/tool invocation."""

    def __init__(self) -> None:
        self._tokens: dict[str, CapabilityToken] = {}

    def issue_token(
        self,
        granted: list[ToolPermissionLevel],
        label: str = "custom",
        valid_seconds: float = 3600.0,
    ) -> CapabilityToken:
        """Issue a new capability token with specific permission grants."""
        expires_at = datetime.now(UTC) + timedelta(seconds=valid_seconds)
        token = CapabilityToken(
            token_id=new_id("cap"),
            granted=granted,
            label=label,
            expires_at=expires_at,
        )
        self._tokens[token.token_id] = token
        return token

    def validate(self, token_id: str, required_permissions: list[ToolPermissionLevel]) -> bool:
        """Validate if token is active and grants all required permissions."""
        token = self._tokens.get(token_id)
        if not token or token.is_expired():
            return False
        grants = token.grants()
        return all(p in grants for p in required_permissions)
