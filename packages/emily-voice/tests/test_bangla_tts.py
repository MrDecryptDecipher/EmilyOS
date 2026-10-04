"""Tests for Roman Bangla detection and TTS prep."""

from __future__ import annotations

from emily.voice.bangla_hints import looks_like_roman_bangla
from emily.voice.language import LanguageDetector
from emily.voice.speech.bangla_tts import prepare_bengali_for_tts, roman_bangla_to_bengali


def test_roman_bangla_to_bengali_common_reply() -> None:
    out = roman_bangla_to_bengali("Haan, ami ekhane achi, apnar sathe kotha bolchi.")
    assert "আমি" in out
    assert "এখানে" in out
    assert "আছি" in out
    assert "আপনি" in out or "আপনার" in out
    assert "Haan" not in out


def test_prepare_bengali_for_tts_passthrough_english() -> None:
    assert prepare_bengali_for_tts("Hello there.", language="en") == "Hello there."


def test_prepare_bengali_for_tts_leaves_bengali_script() -> None:
    text = "হ্যাঁ, আমি এখানেই আছি।"
    assert prepare_bengali_for_tts(text, language="bn") == text


def test_language_detector_roman_bangla() -> None:
    state = LanguageDetector().detect("Tumi kemon acho? Ami bhalo achi.")
    assert state.dominant == "bn"


def test_language_detector_hindi_not_bangla() -> None:
    state = LanguageDetector().detect("Kya haal hai bhai, main theek hoon.")
    assert state.dominant == "hi"


def test_looks_like_roman_bangla_disambiguation() -> None:
    assert looks_like_roman_bangla("apni kemon achhen")
    assert not looks_like_roman_bangla("kya haal hai bhai")
