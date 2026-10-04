"""Policy and capability gates for tool invocation."""

from __future__ import annotations

from typing import Any

from emily.core.types.tool import ToolPermissionLevel
from emily.tools.errors import ToolPermissionError, ToolPolicyError
from emily.tools.models import CapabilityToken, ToolSpec


class PermissionPolicy:
    """Maps Emily settings / capability tokens to allowed permission levels."""

    def __init__(self, settings: Any | None = None) -> None:
        self.settings = settings

    def allowed_levels(self) -> frozenset[ToolPermissionLevel]:
        settings = self.settings
        allowed: set[ToolPermissionLevel] = {ToolPermissionLevel.READ}
        if settings is None:
            # Unbound runtime: local execute only (no desktop/network/privileged).
            allowed.add(ToolPermissionLevel.EXECUTE)
            return frozenset(allowed)

        if bool(getattr(settings, "allow_file_write", False)):
            allowed.add(ToolPermissionLevel.WRITE)
        if bool(getattr(settings, "allow_terminal", False)) or bool(
            getattr(settings, "allow_system_commands", False)
        ):
            allowed.add(ToolPermissionLevel.EXECUTE)
        if bool(getattr(settings, "allow_network", False)):
            allowed.add(ToolPermissionLevel.NETWORK)
        if bool(getattr(settings, "desktop_control", False)):
            allowed.add(ToolPermissionLevel.DESKTOP)
        if bool(getattr(settings, "allow_browser", False)) or bool(
            getattr(settings, "browser_automation", False)
        ):
            allowed.add(ToolPermissionLevel.BROWSER)
        if bool(getattr(settings, "voice_enabled", False)):
            allowed.add(ToolPermissionLevel.VOICE)
        if bool(getattr(settings, "allow_system_commands", False)):
            allowed.add(ToolPermissionLevel.PRIVILEGED)
        # Explicit opt-in for execute even without terminal (offline math tools).
        if bool(getattr(settings, "tool_allow_execute", True)):
            allowed.add(ToolPermissionLevel.EXECUTE)
        return frozenset(allowed)

    def check(
        self,
        spec: ToolSpec,
        *,
        capabilities: CapabilityToken | None = None,
    ) -> frozenset[ToolPermissionLevel]:
        required = frozenset(spec.permissions)
        policy = self.allowed_levels()
        missing_policy = required - policy
        if missing_policy:
            levels = ", ".join(sorted(level.value for level in missing_policy))
            raise ToolPolicyError(
                f"policy denies permissions: {levels}",
                tool_name=spec.name,
            )

        if capabilities is not None:
            if capabilities.is_expired():
                raise ToolPermissionError(
                    "capability token expired",
                    tool_name=spec.name,
                )
            granted = capabilities.grants()
            missing_cap = required - granted
            if missing_cap:
                levels = ", ".join(sorted(level.value for level in missing_cap))
                raise ToolPermissionError(
                    f"capability token missing permissions: {levels}",
                    tool_name=spec.name,
                )
            return required

        return required
