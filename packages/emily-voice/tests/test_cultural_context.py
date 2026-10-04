"""Tests for cultural / contextual reply language."""

from __future__ import annotations

from emily.voice.speech.cultural_context import (
    cultural_reply_guidance,
    infer_reply_language,
    looks_like_playful_challenge,
)


def test_impress_me_detected_as_playful() -> None:
    assert looks_like_playful_challenge("Hey Emily, impress me")


def test_impress_me_uses_bengali_preference() -> None:
    lang = infer_reply_language(
        "impress me",
        detected="en",
        session_dominant="en",
        preferred="bn",
    )
    assert lang == "bn"


def test_bengali_script_wins_over_english_detect() -> None:
    lang = infer_reply_language(
        "তুমি কেমন আছো",
        detected="en",
        preferred=None,
    )
    assert lang == "bn"


def test_french_stays_french() -> None:
    lang = infer_reply_language(
        "quelle heure est-il",
        detected="fr",
        preferred="bn",
    )
    assert lang == "fr"


def test_cultural_guidance_for_bengali_impress() -> None:
    guidance = cultural_reply_guidance("impress me", "bn")
    assert guidance is not None
    assert "Bengali script" in guidance
    assert "মারবো" in guidance or "playful" in guidance.lower()


def test_no_cultural_guidance_for_factual_question() -> None:
    assert cultural_reply_guidance("what time is it", "en") is None
