"""Prosody helpers — pace/pitch/energy from personality."""

from __future__ import annotations

from emily.voice.models import SpeechStyle, VoicePersonality


def compute_pace(personality: VoicePersonality, style: SpeechStyle) -> float:
    pace = float(personality.speaking_rate)
    if style == SpeechStyle.EXCITED:
        pace *= 1.02
    elif style == SpeechStyle.FRIENDLY:
        pace *= 0.98
    elif style == SpeechStyle.WARM:
        pace *= 0.90
    elif style in {SpeechStyle.CALM, SpeechStyle.EMPATHETIC, SpeechStyle.CONCERNED}:
        pace *= 0.86
    elif style == SpeechStyle.TECHNICAL:
        pace *= 0.92
    return max(0.80, min(0.96, pace))


def compute_pitch(personality: VoicePersonality, style: SpeechStyle) -> float:
    pitch = (personality.warmth - 0.5) * 0.12
    if style == SpeechStyle.EXCITED:
        pitch += 0.04
    elif style in {SpeechStyle.FRIENDLY, SpeechStyle.WARM}:
        pitch += 0.04
    elif style == SpeechStyle.PROFESSIONAL:
        pitch -= 0.04
    return max(-0.25, min(0.22, pitch))


def compute_energy(personality: VoicePersonality, style: SpeechStyle) -> float:
    energy = float(personality.energy)
    if style == SpeechStyle.EXCITED:
        energy = min(0.58, energy + 0.04)
    elif style in {SpeechStyle.FRIENDLY, SpeechStyle.WARM}:
        energy = min(0.52, energy + 0.02)
    if style == SpeechStyle.CALM:
        energy = max(0.28, energy - 0.10)
    # Soft ceiling — keep delivery light and sweet, never sharp or loud.
    return max(0.20, min(0.48, energy))
