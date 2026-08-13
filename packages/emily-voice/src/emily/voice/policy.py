"""Voice policy gate."""

from __future__ import annotations

from typing import Any

from emily.voice.errors import VoicePolicyError


class VoicePolicy:
    """Enforces settings-based allow/deny for voice actions."""

    def __init__(self, settings: Any | None = None) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        if self.settings is None:
            return True
        return bool(getattr(self.settings, "voice_enabled", False))

    def require_voice(self) -> None:
        if not self.enabled:
            raise VoicePolicyError("voice_enabled is disabled")
