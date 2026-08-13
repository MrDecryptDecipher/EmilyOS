"""Pause profiles derived from punctuation — never random fillers."""

from __future__ import annotations

from emily.voice.models import PauseProfile

# Duration hints in milliseconds for silence insertion.
PAUSE_MS: dict[PauseProfile, float] = {
    PauseProfile.NONE: 0.0,
    PauseProfile.MICRO: 80.0,
    PauseProfile.SHORT: 180.0,
    PauseProfile.MEDIUM: 320.0,
    PauseProfile.LONG: 550.0,
    PauseProfile.NATURAL: 220.0,
}


def pause_after_text(text: str, *, default: PauseProfile = PauseProfile.NATURAL) -> PauseProfile:
    stripped = text.rstrip()
    if not stripped:
        return PauseProfile.NONE
    if stripped.endswith(("...", "…")):
        return PauseProfile.LONG
    if stripped.endswith(("?", "!")):
        return PauseProfile.MEDIUM
    if stripped.endswith(":"):
        return PauseProfile.SHORT
    if stripped.endswith(";"):
        return PauseProfile.SHORT
    if stripped.endswith(","):
        return PauseProfile.MICRO
    if stripped.endswith("."):
        return default
    return PauseProfile.MICRO


def pause_duration_ms(profile: PauseProfile) -> float:
    return PAUSE_MS.get(profile, PAUSE_MS[PauseProfile.NATURAL])
