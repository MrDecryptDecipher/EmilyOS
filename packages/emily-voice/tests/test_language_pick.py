"""ASR language hint tests."""

from __future__ import annotations

from emily.voice.asr.language_pick import detect_language_hint_from_text


def test_detect_language_hint_bengali_script() -> None:
    assert detect_language_hint_from_text("আপনি কেমন আছেন?") == "bn"


def test_detect_language_hint_telugu_script() -> None:
    assert detect_language_hint_from_text("మీరు ఎలా ఉన్నారు?") == "te"


def test_detect_language_hint_telugu_roman() -> None:
    assert detect_language_hint_from_text("nenu bagundi ela unnaru") == "te"


def test_detect_language_hint_hinglish() -> None:
    assert detect_language_hint_from_text("kya haal hai bhai") == "hi"
