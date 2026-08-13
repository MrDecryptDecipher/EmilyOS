"""Sentence segmentation for streaming TTS."""

from __future__ import annotations

import re

from emily.voice.language import LanguageDetector, script_counts
from emily.voice.models import PauseProfile, SpeechSegment
from emily.voice.speech.pauses import pause_after_text

_SENTENCE_SPLIT = re.compile(
    r"(?<=[.!?।؟])\s+|(?<=\n)\s*",
)


def _lang_for_char(ch: str) -> str:
    if ch.isspace() or ch.isdigit() or ch in ".,!?;:'\"-()[]{}…":
        return "neutral"
    counts = script_counts(ch)
    ranked = counts.most_common()
    if not ranked or ranked[0][0] in {"other", "neutral"}:
        return "en"
    lang = ranked[0][0]
    if lang == "mr":
        return "hi"
    return lang


def split_script_runs(text: str, *, default_language: str = "en") -> list[tuple[str, str]]:
    """
    Split mixed-script text into (language, substring) runs for code-switch TTS.

    Example: "OK, transaction ho gaya." -> [("en", "OK,"), ("hi", "transaction ho gaya.")]
    """
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return []
    runs: list[tuple[str, str]] = []
    current_lang = default_language
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, current_lang
        piece = "".join(buf).strip()
        if piece:
            runs.append((current_lang, piece))
        buf = []

    for ch in cleaned:
        lang = _lang_for_char(ch)
        if lang == "neutral":
            buf.append(ch)
            continue
        if not buf:
            current_lang = lang
            buf.append(ch)
            continue
        if lang == current_lang:
            buf.append(ch)
        else:
            flush()
            current_lang = lang
            buf.append(ch)
    flush()
    return runs if runs else [(default_language, cleaned)]


def detect_segment_language(text: str, *, fallback: str = "en") -> str:
    state = LanguageDetector().detect(text)
    return state.dominant or fallback


def split_sentences(text: str) -> list[str]:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return []
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(cleaned) if p and p.strip()]
    if not parts:
        return [cleaned]
    # Prefer short spoken sentences: soft-split long clauses on commas/semicolons
    result: list[str] = []
    for part in parts:
        if len(part) <= 220:
            result.append(part)
            continue
        soft = re.split(r"(?<=[,;:])\s+", part)
        buf = ""
        for piece in soft:
            candidate = f"{buf} {piece}".strip() if buf else piece
            if len(candidate) > 220 and buf:
                result.append(buf)
                buf = piece
            else:
                buf = candidate
        if buf:
            result.append(buf)
    return result


def segment_for_speech(
    text: str,
    *,
    language: str | None = None,
    pause_profile: PauseProfile = PauseProfile.NATURAL,
    code_switching: bool = False,
    secondary_language: str | None = None,
) -> list[SpeechSegment]:
    dominant = (language or "en").split("-")[0].lower()
    sentences = split_sentences(text)
    segments: list[SpeechSegment] = []
    for sentence in sentences:
        pause = pause_after_text(sentence, default=pause_profile)
        if code_switching:
            runs = split_script_runs(sentence, default_language=dominant)
            if len(runs) <= 1:
                # Romanized Hinglish is all Latin — detect intent, don't tag as English.
                seg_lang = detect_segment_language(sentence, fallback=dominant)
                segments.append(
                    SpeechSegment(text=sentence, pause_after=pause, language=seg_lang)
                )
                continue
            for idx, (run_lang, run_text) in enumerate(runs):
                segments.append(
                    SpeechSegment(
                        text=run_text,
                        pause_after=pause if idx == len(runs) - 1 else PauseProfile.MICRO,
                        language=run_lang,
                    )
                )
            continue
        seg_lang = detect_segment_language(sentence, fallback=dominant)
        if secondary_language and seg_lang == dominant:
            # Hinglish romanized text may detect as hi while plan says en+hi
            pass
        segments.append(
            SpeechSegment(text=sentence, pause_after=pause, language=seg_lang or dominant)
        )
    return segments
