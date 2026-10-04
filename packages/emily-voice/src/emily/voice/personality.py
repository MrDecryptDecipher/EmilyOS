"""Voice personality persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from emily.voice.models import SpeechStyle, VoicePersonality

DEFAULT_PERSONALITY = VoicePersonality(
    name="Emily",
    warmth=0.96,
    energy=0.34,
    formality=0.18,
    expressiveness=0.52,
    speaking_rate=0.84,
    default_language="en-IN",
    default_style=SpeechStyle.WARM,
    voice_name="af_bella",
)


def default_personality_path(settings: Any | None = None) -> Path:
    if settings is not None:
        override = getattr(settings, "voice_personality_path", None)
        if override:
            return Path(override)
        data_dir = getattr(settings, "voice_directory", None)
        if data_dir:
            return Path(data_dir) / "personality.json"
    return Path("data/voice/personality.json")


def load_personality(path: Path | str | None = None, *, settings: Any | None = None) -> VoicePersonality:
    target = Path(path) if path is not None else default_personality_path(settings)
    if not target.exists():
        return DEFAULT_PERSONALITY.model_copy(deep=True)
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return DEFAULT_PERSONALITY.model_copy(deep=True)
    return VoicePersonality.model_validate({**DEFAULT_PERSONALITY.model_dump(), **raw})


BENGALI_IMPRESS_RESPONSE_PHONETIC = "Maarbo Ekhaane, Laash Porbe Shoshaane"
BENGALI_IMPRESS_RESPONSE_BENGLI = "মারবো এখানে, লাশ পড়বে শ্মশানে"


def check_impress_context(text: str) -> str | None:
    """Check if the user request matches the impress context phrase.

    Returns the iconic Bengali response when matched.
    """
    normalized = text.lower().strip()
    keywords = ["impress me", "hey emily impress me", "impress", "amake impress koro", "bengali impress"]
    if any(k in normalized for k in keywords):
        return BENGALI_IMPRESS_RESPONSE_PHONETIC
    return None


def save_personality(
    personality: VoicePersonality,
    path: Path | str | None = None,
    *,
    settings: Any | None = None,
) -> Path:
    target = Path(path) if path is not None else default_personality_path(settings)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(personality.model_dump_json(indent=2), encoding="utf-8")
    return target
