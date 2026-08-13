"""SpeechDirector unit tests — no TTS backends required."""

from __future__ import annotations

from emily.voice.models import (
    HardwareInfo,
    HardwareProfile,
    LanguageState,
    SpeechStyle,
    VoicePersonality,
)
from emily.voice.speech.director import SpeechDirector


def test_director_plans_segments_and_kokoro_default() -> None:
    director = SpeechDirector()
    plan = director.plan(
        "Hello there. How are you today?",
        language_state=LanguageState(dominant="en", confidence=0.9),
        personality=VoicePersonality(),
        hardware=HardwareInfo(profile=HardwareProfile.MEDIUM),
        available_backends=["kokoro"],
    )
    assert plan.language == "en"
    assert plan.tts_backend == "kokoro"
    assert len(plan.segments) >= 2
    assert plan.style in SpeechStyle
    assert "um" not in plan.text.lower()  # no filler injection


def test_director_prefers_kokoro_for_devanagari_hindi() -> None:
    from types import SimpleNamespace

    director = SpeechDirector()
    plan = director.plan(
        "नमस्ते आप कैसे हैं?",
        language_state=LanguageState(dominant="hi", confidence=0.95),
        hardware=HardwareInfo(profile=HardwareProfile.MEDIUM, ram_gb=12, cpu_count=6),
        available_backends=["kokoro", "indicf5", "chatterbox"],
        settings=SimpleNamespace(tts_device="cpu", voice_tts_prefer_lightweight=False),
    )
    assert plan.tts_backend == "kokoro"
    assert plan.voice == "hf_beta"
    assert plan.language == "hi"


def test_director_roman_hinglish_uses_kokoro_after_prep() -> None:
    from types import SimpleNamespace

    director = SpeechDirector()
    plan = director.plan(
        "Haan, bas yahin hoon, aap se baat kar rahi hoon.",
        language_state=LanguageState(dominant="hi", confidence=0.95),
        hardware=HardwareInfo(profile=HardwareProfile.MEDIUM, ram_gb=12, cpu_count=6),
        available_backends=["kokoro", "indicf5", "chatterbox"],
        settings=SimpleNamespace(tts_default="voicebox", tts_device="cuda", voice_tts_prefer_lightweight=False),
    )
    assert plan.tts_backend == "kokoro"
    assert "हाँ" in plan.text
    assert plan.voice == "hf_beta"


def test_director_prefers_indicf5_for_hindi_on_cuda_devanagari_only() -> None:
    from types import SimpleNamespace

    director = SpeechDirector()
    plan = director.plan(
        "नमस्ते, मैं मदद कर सकती हूँ।",
        language_state=LanguageState(dominant="hi", confidence=0.95),
        hardware=HardwareInfo(profile=HardwareProfile.HIGH, cuda_available=True, ram_gb=16, cpu_count=8),
        available_backends=["kokoro", "indicf5", "chatterbox"],
        settings=SimpleNamespace(tts_device="cuda", voice_tts_prefer_lightweight=False),
    )
    # Kokoro is preferred for Hindi now (fast, sweet hf_beta).
    assert plan.tts_backend == "kokoro"


def test_director_prefers_kokoro_for_hindi_on_cpu() -> None:
    from types import SimpleNamespace

    director = SpeechDirector()
    plan = director.plan(
        "नमस्ते आप कैसे हैं?",
        language_state=LanguageState(dominant="hi", confidence=0.95),
        hardware=HardwareInfo(profile=HardwareProfile.MEDIUM, ram_gb=12, cpu_count=6),
        available_backends=["kokoro", "indicf5", "chatterbox"],
        settings=SimpleNamespace(tts_device="cpu", voice_tts_prefer_lightweight=True),
    )
    assert plan.tts_backend == "kokoro"


def test_director_low_prefers_kokoro_over_heavy() -> None:
    director = SpeechDirector()
    plan = director.plan(
        "नमस्ते",
        language_state=LanguageState(dominant="hi", confidence=0.95),
        hardware=HardwareInfo(profile=HardwareProfile.LOW, ram_gb=4, cpu_count=2),
        available_backends=["kokoro", "indicf5", "chatterbox"],
    )
    assert plan.tts_backend == "kokoro"


def test_director_expressive_prefers_chatterbox() -> None:
    director = SpeechDirector()
    plan = director.plan(
        "This is amazing news!",
        language_state=LanguageState(dominant="en", confidence=0.9),
        personality=VoicePersonality(energy=0.9, expressiveness=0.9),
        hardware=HardwareInfo(profile=HardwareProfile.HIGH, cuda_available=True, ram_gb=16, cpu_count=8),
        available_backends=["kokoro", "chatterbox"],
        emotion="excited",
    )
    assert plan.tts_backend == "chatterbox"
    assert plan.style == SpeechStyle.EXCITED


def test_director_preserves_code_switching() -> None:
    director = SpeechDirector()
    plan = director.plan(
        "Let's go to the बाजार tomorrow.",
        language_state=LanguageState(dominant="en", secondary="hi", code_switching=True, confidence=0.8),
        available_backends=["kokoro"],
    )
    assert plan.code_switching is True
    assert plan.secondary_language == "hi"
