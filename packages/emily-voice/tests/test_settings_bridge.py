"""Settings bridge enable-flag filtering."""

from __future__ import annotations

from types import SimpleNamespace

from emily.voice.models import TTSCapability
from emily.voice.settings_bridge import enabled_backends, resolve_device, voice_flag


class _E:
    def __init__(self, name: str) -> None:
        self.name = name
        self.capabilities = TTSCapability(name=name, languages=["en"])

    def available(self) -> bool:
        return True


def test_enabled_backends_filters_flags() -> None:
    engines = {n: _E(n) for n in ("kokoro", "indicf5", "chatterbox")}
    settings = SimpleNamespace(
        tts_enable_kokoro=True,
        tts_enable_indicf5=False,
        tts_enable_chatterbox=False,
        tts_device="cpu",
    )
    out = enabled_backends(settings, engines)
    assert list(out.keys()) == ["kokoro"]


def test_voice_flag_and_device() -> None:
    assert voice_flag(None, "voice_barge_in", True) is True
    settings = SimpleNamespace(tts_device="cpu", voice_emotion=False)
    assert voice_flag(settings, "voice_emotion", True) is False
    assert resolve_device(settings) == "cpu"
