"""Bangla wake hint tests."""

from __future__ import annotations

from emily.voice.bangla_hints import wake_english_likely_indic_speech


def test_wake_english_likely_indic_for_how_are_you() -> None:
    assert wake_english_likely_indic_speech("how are you?")


def test_wake_english_likely_indic_for_tumi_kemon() -> None:
    assert wake_english_likely_indic_speech("tumi kemon acho")


def test_wake_english_likely_indic_false_for_factual_english() -> None:
    assert not wake_english_likely_indic_speech("what time is it")
