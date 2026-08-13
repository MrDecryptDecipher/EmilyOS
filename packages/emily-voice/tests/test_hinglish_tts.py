"""Tests for Roman Hinglish → Devanagari TTS prep."""

from __future__ import annotations

from emily.voice.speech.hinglish_tts import prepare_hindi_for_tts, roman_hinglish_to_devanagari


def test_roman_hinglish_to_devanagari_common_reply() -> None:
    out = roman_hinglish_to_devanagari("Haan, bas yahin hoon, aap se baat kar rahi hoon.")
    assert "हाँ" in out
    assert "यहीं" in out
    assert "आप" in out
    assert "बात" in out
    assert "रही" in out
    assert "Haan" not in out


def test_prepare_hindi_for_tts_passthrough_english() -> None:
    assert prepare_hindi_for_tts("Hello there.", language="en") == "Hello there."


def test_prepare_hindi_for_tts_leaves_devanagari() -> None:
    text = "हाँ, बस यहीं हूँ।"
    assert prepare_hindi_for_tts(text, language="hi") == text
