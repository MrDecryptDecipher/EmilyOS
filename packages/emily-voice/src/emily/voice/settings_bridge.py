"""Bridge EmilySettings voice flags into runtime TTS / device decisions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from emily.voice.hardware import resolve_torch_device

if TYPE_CHECKING:
    from emily.voice.tts.base import TTSEngine


_ENABLE_FLAGS: dict[str, str] = {
    "kokoro": "tts_enable_kokoro",
    "indicf5": "tts_enable_indicf5",
    "chatterbox": "tts_enable_chatterbox",
    "voicebox": "tts_enable_voicebox",
}


def voice_flag(settings: Any | None, name: str, default: Any = None) -> Any:
    """Read a voice-related setting with a safe default."""
    if settings is None:
        return default
    return getattr(settings, name, default)


def enabled_backends(
    settings: Any | None,
    engines: Mapping[str, TTSEngine],
) -> dict[str, TTSEngine]:
    """Keep only production TTS backends enabled via tts_enable_* flags."""
    out: dict[str, Any] = {}
    for name, engine in engines.items():
        flag = _ENABLE_FLAGS.get(name)
        if flag is None:
            continue
        if bool(voice_flag(settings, flag, True)):
            out[name] = engine
    return out  # type: ignore[return-value]


def resolve_device(settings: Any | None) -> str:
    """Map tts_device (auto|cpu|cuda|mps) onto a concrete torch device string."""
    prefer = str(voice_flag(settings, "tts_device", "auto") or "auto")
    return resolve_torch_device(prefer)


def prefer_lightweight_tts(settings: Any | None) -> bool:
    """On CPU, prefer Kokoro over slow IndicF5/Chatterbox unless explicitly disabled."""
    if not bool(voice_flag(settings, "voice_tts_prefer_lightweight", True)):
        return False
    return resolve_device(settings) == "cpu"
