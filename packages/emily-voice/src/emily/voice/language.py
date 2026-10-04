"""Language detection with sticky LanguageState."""

from __future__ import annotations

import re
from collections import Counter

from emily.voice.bangla_hints import bangla_hint_score, hinglish_disambig_score
from emily.voice.models import LanguageState

# Unicode script ranges for major Indic languages + Latin.
_SCRIPT_RANGES: dict[str, tuple[tuple[int, int], ...]] = {
    "hi": ((0x0900, 0x097F),),  # Devanagari (also mr/ne)
    "mr": ((0x0900, 0x097F),),
    "te": ((0x0C00, 0x0C7F),),  # Telugu
    "or": ((0x0B00, 0x0B7F),),  # Odia
    "bn": ((0x0980, 0x09FF),),  # Bengali
    "ta": ((0x0B80, 0x0BFF),),  # Tamil
    "kn": ((0x0C80, 0x0CFF),),  # Kannada
    "ml": ((0x0D00, 0x0D7F),),  # Malayalam
    "gu": ((0x0A80, 0x0AFF),),  # Gujarati
    "pa": ((0x0A00, 0x0A7F),),  # Gurmukhi
    "en": ((0x0041, 0x007A), (0x00C0, 0x024F)),  # Latin + Latin Extended
}

_HINGLISH_HINTS = re.compile(
    r"\b("
    r"hai|hain|hoon|hun|main|mein|mujhe|aap|aapke|aapka|tum|tumhe|"
    r"kya|nahi|nahin|acha|accha|theek|yaar|bhai|ji|mat|"
    r"karo|karna|kar|karke|kar rahi|kar raha|rahe|raha|rahi|"
    r"kyun|kyu|haal|hal|chaal|chal|kaise|kaisa|"
    r"saath|sath|baat|madad|sakti|sakta|chahiye|"
    r"mujhe|hum|humne|karte|karti"
    r")\b",
    re.IGNORECASE,
)

_INDIAN_LANGS = frozenset({"hi", "mr", "te", "or", "bn", "ta", "kn", "ml", "gu", "pa", "as"})


def has_devanagari(text: str) -> bool:
    """True when text contains Devanagari script (Hindi/Marathi)."""
    return any("\u0900" <= ch <= "\u097F" for ch in text)


def has_bengali(text: str) -> bool:
    """True when text contains Bengali script."""
    return any("\u0980" <= ch <= "\u09FF" for ch in text)


def latin_letter_share(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    latin = sum(1 for ch in letters if "A" <= ch.upper() <= "Z")
    return latin / len(letters)


def is_romanized_hinglish(text: str) -> bool:
    """
    Romanized Hindi/Hinglish in Latin letters.

    Kokoro's Hindi pipeline expects Devanagari — feeding Latin causes phonemizer
    language-switch warnings and a wrong accent. Route these to IndicF5 instead.
    """
    cleaned = (text or "").strip()
    if not cleaned or has_devanagari(cleaned):
        return False
    if latin_letter_share(cleaned) < 0.45:
        return False
    detected = LanguageDetector().detect(cleaned)
    return detected.dominant == "hi" or bool(_HINGLISH_HINTS.search(cleaned))


def _char_in_ranges(ch: str, ranges: tuple[tuple[int, int], ...]) -> bool:
    code = ord(ch)
    return any(start <= code <= end for start, end in ranges)


def script_counts(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for ch in text:
        if ch.isspace() or ch.isdigit() or ch in ".,!?;:'\"-()[]{}":
            continue
        matched = False
        for lang, ranges in _SCRIPT_RANGES.items():
            if lang == "mr":
                continue  # counted via hi/Devanagari
            if _char_in_ranges(ch, ranges):
                counts[lang] += 1
                matched = True
                break
        if not matched:
            counts["other"] += 1
    return counts


class LanguageDetector:
    """Heuristic language detector with sticky updates."""

    def __init__(self, *, stickiness: float = 0.65, flip_margin: float = 0.18) -> None:
        self.stickiness = stickiness
        self.flip_margin = flip_margin
        self.state = LanguageState()

    def detect(self, text: str) -> LanguageState:
        counts = script_counts(text)
        total = sum(counts.values()) or 1
        ranked = counts.most_common()
        primary = ranked[0][0] if ranked else "en"
        primary_share = (ranked[0][1] / total) if ranked else 0.0
        secondary: str | None = None
        code_switching = False

        if primary == "other":
            primary = "en"

        # Hinglish: Latin script with Hindi romanized cues
        if primary == "en" and _HINGLISH_HINTS.search(text):
            b_score = bangla_hint_score(text)
            h_score = max(len(_HINGLISH_HINTS.findall(text)), hinglish_disambig_score(text))
            if b_score >= 2 and b_score > h_score:
                primary = "bn"
                secondary = "en"
                code_switching = True
                primary_share = max(primary_share, 0.55)
            else:
                primary = "hi"
                secondary = "en"
                code_switching = True
                primary_share = max(primary_share, 0.55)
        elif primary == "en" and bangla_hint_score(text) >= 2:
            primary = "bn"
            secondary = "en"
            code_switching = True
            primary_share = max(primary_share, 0.55)

        if len(ranked) >= 2 and ranked[1][0] not in {"other"}:
            second_lang, second_count = ranked[1]
            second_share = second_count / total
            if second_share >= 0.12 and second_lang != primary:
                secondary = second_lang
                code_switching = True

        # Prefer hi for Devanagari unless explicitly marked otherwise
        if primary == "mr":
            primary = "hi"

        confidence = min(0.99, 0.35 + primary_share * 0.65)
        return LanguageState(
            dominant=primary,
            secondary=secondary,
            confidence=confidence,
            code_switching=code_switching,
            detected_language=primary,
            sticky=True,
        )

    def update(self, text: str, *, user_language_preference: str | None = None) -> LanguageState:
        detected = self.detect(text)
        sticky = self.state.sticky
        pref = user_language_preference or self.state.user_language_preference
        if not self.state.dominant:
            self.state = detected.model_copy(
                update={"sticky": sticky, "user_language_preference": pref, "detected_language": detected.dominant}
            )
            return self.state

        if not sticky:
            self.state = detected.model_copy(
                update={"sticky": False, "user_language_preference": pref, "detected_language": detected.dominant}
            )
            return self.state

        # Sticky: only flip when new detection is confidently different
        same = detected.dominant == self.state.dominant
        if same:
            self.state = LanguageState(
                dominant=self.state.dominant,
                secondary=detected.secondary or self.state.secondary,
                confidence=min(
                    0.99,
                    self.state.confidence * self.stickiness + detected.confidence * (1 - self.stickiness),
                ),
                code_switching=detected.code_switching or self.state.code_switching,
                detected_language=detected.dominant,
                user_language_preference=pref,
                sticky=True,
            )
            return self.state

        if detected.confidence >= self.state.confidence + self.flip_margin:
            self.state = detected.model_copy(
                update={
                    "sticky": True,
                    "user_language_preference": pref,
                    "detected_language": detected.dominant,
                }
            )
        else:
            # Keep dominant; maybe note secondary for code-switch
            self.state = LanguageState(
                dominant=self.state.dominant,
                secondary=detected.dominant,
                confidence=self.state.confidence * 0.9,
                code_switching=True,
                detected_language=detected.dominant,
                user_language_preference=pref,
                sticky=True,
            )
        return self.state

    def reset(self, *, dominant: str = "en") -> None:
        self.state = LanguageState(dominant=dominant, confidence=0.5, sticky=True)

    @staticmethod
    def is_indian(lang: str) -> bool:
        base = lang.split("-")[0].lower()
        return base in _INDIAN_LANGS
