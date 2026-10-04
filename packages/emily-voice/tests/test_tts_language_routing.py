"""TTS language capability tests."""

from __future__ import annotations

from types import SimpleNamespace

from emily.voice.settings_bridge import effective_engines_for_language
from emily.voice.tts.registry import kokoro_supports, language_requires_indicf5


def test_kokoro_does_not_support_bengali() -> None:
    assert not kokoro_supports("bn")
    assert kokoro_supports("hi")
    assert kokoro_supports("en")


def test_bengali_requires_indicf5() -> None:
    assert language_requires_indicf5("bn")
    assert not language_requires_indicf5("en")


def test_effective_engines_includes_indicf5_for_bengali_when_flag_off() -> None:
    class _Indic:
        name = "indicf5"

        def available(self) -> bool:
            return True

    class _Kokoro:
        name = "kokoro"

        def available(self) -> bool:
            return True

    all_eng = {"kokoro": _Kokoro(), "indicf5": _Indic()}  # type: ignore[dict-item]
    enabled = {"kokoro": _Kokoro()}  # type: ignore[dict-item]
    settings = SimpleNamespace(tts_enable_indicf5=False, tts_enable_kokoro=True)
    out = effective_engines_for_language(settings, enabled, all_eng, "bn")
    assert "indicf5" in out
    assert "kokoro" in out
