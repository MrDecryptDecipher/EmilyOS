"""ASR language retry heuristics."""

from __future__ import annotations

from emily.voice.asr.language_pick import (
    looks_like_english_hallucination,
    pick_best_transcription,
    should_retry_transcription,
)


def test_should_retry_low_confidence_english() -> None:
    assert should_retry_transcription(
        "Alright, alright. Yeah, alright, let's go.",
        "en",
        0.29,
    )


def test_hallucination_detector() -> None:
    assert looks_like_english_hallucination("alright alright let's go", language_probability=0.29)
    assert not looks_like_english_hallucination("नमस्ते, क्या हाल है?", language_probability=0.8)


def test_wake_hallucination_filtered() -> None:
    from emily.voice.asr.language_pick import looks_like_wake_hallucination

    assert looks_like_wake_hallucination("Thank you very much. You're welcome.")
    assert looks_like_wake_hallucination("you")
    assert looks_like_wake_hallucination("You")
    assert not looks_like_wake_hallucination("Hey Emily, kya haal hai?")
    assert not looks_like_wake_hallucination("Hry Emily what's up")


def test_pick_indic_over_hallucination() -> None:
    auto = ("Alright, alright. Yeah, alright, let's go.", "en", 0.29)
    hindi = ("नमस्ते, आज मौसम कैसा है?", "hi", 0.71)
    text, lang, prob = pick_best_transcription([auto, hindi])
    assert lang == "hi"
    assert "नमस्ते" in text
    assert prob == 0.71


def test_pick_hindi_over_tamil_when_hint_hi() -> None:
    tamil = ("ஹெய்ய மிலி ஏன் கால் சால்", "ta", 1.0)
    hindi = ("हे एमिली क्या हाल चाल", "hi", 0.62)
    text, lang, _prob = pick_best_transcription([tamil, hindi], language_hint="hi")
    assert lang == "hi"
    assert "हाल" in text or "एमिली" in text
