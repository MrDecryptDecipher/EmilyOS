"""Romanized Bangla cues — shared by ASR hints, language detection, and wake follow-ups."""

from __future__ import annotations

import re

def _has_bengali(text: str) -> bool:
    return any("\u0980" <= ch <= "\u09FF" for ch in text)


def _has_devanagari(text: str) -> bool:
    return any("\u0900" <= ch <= "\u097F" for ch in text)

# Bengali-specific roman tokens (avoid Hindi overlaps like kya, tum, ki alone).
_BANGLA_HINTS = re.compile(
    r"\b("
    r"kemon|keno|kothay|kotha|khobor|tumi|tomar|tomake|bhalo|valo|bhalob|hobe|"
    r"bolchi|boltesi|bolte|bolo|lagche|lagbe|dhonnobad|nomoshkar|nomoskar|shubho|"
    r"ekhon|akhon|ekhane|ekhan|onek|khub|apnar|amar|achhi|achi|achhe|ache|"
    r"parbo|parbi|jani|shono|kichu|kokhon|kivabe|kibhabe|janina|janbo|"
    r"kemon acho|ki khobor|bhalo achho|bhalo achhe"
    r")\b",
    re.IGNORECASE,
)

# Hindi tokens used to disambiguate roman text that could be either language.
_HINGLISH_DISAMBIG = re.compile(
    r"\b("
    r"kya|kaise|kaisa|nahi|nahin|haan|han|mujhe|aapka|aapke|aapki|karo|karna|"
    r"theek|thik|accha|achha|haal|hal|chaal|chal|chahiye|madad|rahi|raha|rahe"
    r")\b",
    re.IGNORECASE,
)

_GENERIC_BANGLA_GREETING = re.compile(
    r"^(?:kemon acho|kemon achho|ki khobor|apni kemon achhen)(?:\?|\.|!)?$",
    re.IGNORECASE,
)

# Whisper often translates spoken Bengali into fluent but wrong English on the wake path.
_LIKELY_BENGALI_MISHEARD_AS_ENGLISH = re.compile(
    r"\b("
    r"gonna show|going to show|i'?m gonna show|do you think i'?m|do you think i am|"
    r"think i'?m gonna|kemon acho|achio|achho|how are you doing today"
    r")\b",
    re.IGNORECASE,
)

# English fragments Whisper emits for Indic speech — never trust on wake follow-ups.
_UNLIKELY_VOICE_ASSISTANT_ENGLISH = re.compile(
    r"\b("
    r"gonna show|going to show|i'?m gonna show|do you think i'?m|do you think i am|"
    r"think i'?m gonna|thank you for watching|thanks for watching|"
    r"you'?re welcome|please subscribe|see you next time|where are you going"
    r")\b",
    re.IGNORECASE,
)


def bangla_hint_score(text: str) -> int:
    return len(_BANGLA_HINTS.findall(text or ""))


def hinglish_disambig_score(text: str) -> int:
    return len(_HINGLISH_DISAMBIG.findall(text or ""))


def looks_like_roman_bangla(text: str) -> bool:
    """True when romanized text is more likely Bangla than Hindi/Hinglish."""
    cleaned = (text or "").strip()
    if not cleaned or _has_bengali(cleaned) or _has_devanagari(cleaned):
        return _has_bengali(cleaned)
    b_score = bangla_hint_score(cleaned)
    if b_score == 0:
        return False
    h_score = hinglish_disambig_score(cleaned)
    if b_score >= 2:
        return b_score > h_score
    return b_score >= 1 and h_score == 0


# English wake follow-up — Whisper often translates spoken Bengali/Hindi into this.
_LIKELY_INDIC_WAKE_ENGLISH = re.compile(
    r"\b("
    r"what'?s up|how are you|how are you doing|how'?s it going|what are you doing|"
    r"what are you up to|how have you been|how'?s everything|how is it going|"
    r"how you doing|kemon acho|kemon achho|tumi kemon"
    r")\b",
    re.IGNORECASE,
)


def wake_english_likely_indic_speech(text: str) -> bool:
    """
    True when English wake follow-up probably means the user spoke Bengali/Hindi.

    Example: user says «Hey Emily, tumi kemon acho» → wake ASR hears «how are you».
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    if looks_like_roman_bangla(cleaned) or _has_bengali(cleaned):
        return True
    return bool(_LIKELY_INDIC_WAKE_ENGLISH.search(cleaned)) or looks_like_bengali_misheard_as_english(
        cleaned
    )


def looks_like_generic_bangla_greeting(text: str) -> bool:
    return bool(_GENERIC_BANGLA_GREETING.match((text or "").strip()))


def looks_like_bengali_misheard_as_english(text: str) -> bool:
    """English wake ASR text that is probably spoken Bengali mistranscribed."""
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    if looks_like_roman_bangla(cleaned) or _has_bengali(cleaned):
        return False
    return bool(_LIKELY_BENGALI_MISHEARD_AS_ENGLISH.search(cleaned))


def unlikely_voice_assistant_english(text: str) -> bool:
    """Whisper filler / mistranslation — not a real user question for Emily."""
    return bool(_UNLIKELY_VOICE_ASSISTANT_ENGLISH.search(text or ""))
