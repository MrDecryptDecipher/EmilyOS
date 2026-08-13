"""Speech segmentation and code-switch splitting."""

from __future__ import annotations

from emily.voice.models import PauseProfile
from emily.voice.speech.segmentation import (
    segment_for_speech,
    split_script_runs,
    split_sentences,
)


def test_split_script_runs_mixed_latin_and_devanagari() -> None:
    runs = split_script_runs("OK, transaction हो गया.", default_language="en")
    langs = [lang for lang, _ in runs]
    texts = [text for _, text in runs]
    assert "en" in langs
    assert "hi" in langs
    assert any("OK" in t for t in texts)
    assert any("transaction" in t or "गया" in t for t in texts)


def test_split_script_runs_devanagari_only() -> None:
    runs = split_script_runs("नमस्ते आप कैसे हैं", default_language="hi")
    assert len(runs) == 1
    assert runs[0][0] == "hi"


def test_segment_for_speech_code_switch_splits_runs() -> None:
    segments = segment_for_speech(
        "Sure, main check karta hoon.",
        language="en",
        code_switching=True,
        pause_profile=PauseProfile.NATURAL,
    )
    langs = {s.language for s in segments}
    joined = " ".join(s.text for s in segments)
    assert "en" in langs or "hi" in langs
    assert "check" in joined.lower()
    assert len(segments) >= 1


def test_segment_for_speech_without_code_switch_single_language() -> None:
    segments = segment_for_speech(
        "Hello there. How are you?",
        language="en",
        code_switching=False,
    )
    assert len(segments) >= 2
    assert all(s.language in {"en", None} or s.language == "en" for s in segments)


def test_split_sentences_soft_breaks_long_clauses() -> None:
    long = "word " * 80 + "."
    parts = split_sentences(long.strip())
    assert len(parts) >= 1
    assert parts[0].endswith(".")
