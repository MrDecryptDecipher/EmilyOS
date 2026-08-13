"""Helpers for choosing Whisper language / transcript when auto-detect is unreliable."""

from __future__ import annotations

import re

from emily.voice.language import script_counts

# Whisper ISO-639-1 codes we retry (Odia `or` is not supported by faster-whisper).
WHISPER_INDIC_LANGUAGES: tuple[str, ...] = (
    "hi",
    "bn",
    "ta",
    "te",
    "mr",
    "gu",
    "kn",
    "ml",
    "pa",
    "as",
)

_TELUGU_ROMAN = re.compile(
    r"\b(nenu|emi|ela|avunu|cheppu|bagundi|sare|ledu|undhi|undi|meeru)\b",
    re.IGNORECASE,
)
_BENGALI_ROMAN = re.compile(
    r"\b(ki|kemon|keno|tumi|ami|apni|bhalo|hobe|ache|achhe|kothay)\b",
    re.IGNORECASE,
)
_ODIA_ROMAN = re.compile(
    r"\b(kana|kemiti|mu|tume|bhala|achhi|kahinki)\b",
    re.IGNORECASE,
)
_HINGLISH_ROMAN = re.compile(
    r"\b("
    r"kya|kaise|kaisa|kaisi|haal|hal|chaal|chal|chahiye|chahie|karo|karna|kar|bata|bhai|"
    r"accha|achha|theek|thik|namaste|mujhe|aap|tum|hai|hoon|hun|nahi|nahin|haan|han|ji|"
    r"kal|aaj|abhi|kaam|madad|rahe|raha|rahi|kyaa"
    r")\b",
    re.IGNORECASE,
)

INDIC_ASR_CANDIDATES: tuple[str, ...] = WHISPER_INDIC_LANGUAGES + ("or",)

_LOW_CONFIDENCE = 0.50
_ENGLISH_HALLUCINATION = re.compile(
    r"\b("
    r"alright|okay|ok+|yeah|let'?s go|thank you for watching|"
    r"thank you very much|you'?re welcome|thanks for watching|"
    r"thanks for listening|please subscribe|silence|music|"
    r"see you next time|goodbye|bye bye"
    r")\b",
    re.IGNORECASE,
)


def indic_script_share(text: str) -> float:
    counts = script_counts(text)
    total = sum(counts.values()) or 1
    indic = sum(counts.get(lang, 0) for lang in INDIC_ASR_CANDIDATES)
    return indic / total


def looks_like_english_hallucination(text: str, *, language_probability: float | None) -> bool:
    """Whisper often emits filler English when the speaker used an Indic language."""
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    if language_probability is not None and language_probability >= 0.72:
        return False
    if indic_script_share(cleaned) >= 0.08:
        return False
    lower = cleaned.lower()
    if _ENGLISH_HALLUCINATION.search(lower):
        return True
    if lower.count("alright") >= 2:
        return True
    # Very short repetitive latin-only fragments with weak detection confidence.
    words = re.findall(r"[a-zA-Z']+", lower)
    if (
        language_probability is not None
        and language_probability < 0.40
        and len(words) <= 8
        and len(set(words)) <= 4
    ):
        return True
    return False


def should_retry_transcription(
    text: str,
    detected_language: str | None,
    language_probability: float | None,
) -> bool:
    if looks_like_english_hallucination(text, language_probability=language_probability):
        return True
    if language_probability is not None and language_probability < _LOW_CONFIDENCE:
        return True
    if detected_language == "en" and language_probability is not None and language_probability < 0.62:
        if indic_script_share(text) < 0.05:
            return True
    return False


def retry_language_order(language_hint: str | None) -> list[str]:
    order: list[str] = []
    if language_hint and language_hint not in {"en", "auto"}:
        base = language_hint.split("-")[0].lower()
        if base == "or":
            # Odia ASR not available in Whisper; try Hindi as closest Devanagari-adjacent fallback.
            if "hi" not in order:
                order.append("hi")
        elif base in WHISPER_INDIC_LANGUAGES and base not in order:
            order.append(base)
    for lang in WHISPER_INDIC_LANGUAGES:
        if lang not in order:
            order.append(lang)
    return order


def score_transcription(
    text: str,
    detected_language: str | None,
    language_probability: float | None,
    *,
    language_hint: str | None = None,
) -> float:
    prob = language_probability if language_probability is not None else 0.0
    score = prob * 100.0
    score += indic_script_share(text) * 80.0
    if looks_like_english_hallucination(text, language_probability=language_probability):
        score -= 120.0
    if text.strip():
        score += min(len(text.strip()) / 4.0, 25.0)
    if detected_language in INDIC_ASR_CANDIDATES:
        score += 10.0

    hint = (language_hint or "").split("-")[0].lower() if language_hint else ""
    if hint and hint not in {"en", "auto"}:
        det = (detected_language or "").split("-")[0].lower()
        counts = script_counts(text)
        if hint == "hi":
            # Strongly prefer Hindi/Devanagari; penalize wrong-script Indic (esp. Tamil).
            if det in {"hi", "mr"} or counts.get("hi", 0) > 0:
                score += 55.0
            wrong = sum(counts.get(lang, 0) for lang in ("ta", "te", "bn", "kn", "ml", "gu", "pa", "as"))
            if wrong > 0 and counts.get("hi", 0) == 0:
                score -= 90.0
            if det in {"ta", "te", "bn", "kn", "ml"} and det != hint:
                score -= 70.0
        elif det == hint or counts.get(hint, 0) > 0:
            score += 55.0
        elif det in INDIC_ASR_CANDIDATES and det != hint:
            score -= 45.0
    return score


def pick_best_transcription(
    candidates: list[tuple[str, str | None, float | None]],
    *,
    language_hint: str | None = None,
) -> tuple[str, str | None, float | None]:
    if not candidates:
        return "", None, None
    best = max(
        candidates,
        key=lambda c: score_transcription(c[0], c[1], c[2], language_hint=language_hint),
    )
    return best


def detect_language_hint_from_text(text: str) -> str | None:
    """Guess Whisper language code from script or romanized Indic cues."""
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    counts = script_counts(cleaned)
    ranked = [(lang, count) for lang, count in counts.most_common() if lang != "other" and count > 0]
    if ranked:
        lang = ranked[0][0]
        if lang == "mr":
            return "hi"
        if lang in WHISPER_INDIC_LANGUAGES:
            return lang
        if lang == "hi":
            return "hi"
    lower = cleaned.lower()
    if _TELUGU_ROMAN.search(lower):
        return "te"
    if _BENGALI_ROMAN.search(lower):
        return "bn"
    if _ODIA_ROMAN.search(lower):
        return "hi"  # Odia not in Whisper; Hindi is closest supported fallback
    if _HINGLISH_ROMAN.search(lower):
        return "hi"
    return None


_GENERIC_EN_FOLLOWUP = re.compile(
    r"\b("
    r"what'?s up|how are you|how can i help|what can i do|hello there|"
    r"what are you doing|what are you up to|how'?s it going|how are you doing"
    r")\b",
    re.IGNORECASE,
)


def looks_like_generic_english_followup(text: str) -> bool:
    return bool(_GENERIC_EN_FOLLOWUP.search(text or ""))


def looks_like_wake_hallucination(text: str, *, wake_phrase: str = "Hey Emily") -> bool:
    """
    Whisper often hallucinates polite English on noise/silence during wake listen.

    Treat as no speech when the transcript lacks the wake name/phrase.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    lower = cleaned.lower()
    if "emily" in lower:
        return False
    if wake_phrase.lower() in lower:
        return False
    if re.search(r"\b(hey|hry|hi|hai|aye)\s*,?\s*emily\b", cleaned, re.IGNORECASE):
        return False
    words = re.findall(r"[a-zA-Z']+", lower)
    # Ultra-short non-wake fragments from over-trimmed clips ("you", "the", "a").
    if len(words) <= 2 and not any(w in {"hey", "hi", "hai", "emily"} for w in words):
        return True
    if looks_like_english_hallucination(cleaned, language_probability=0.55):
        return True
    # Generic courtesy/outro phrases with no wake content.
    if re.search(
        r"\b(thank you|you'?re welcome|thanks for|subscribe|welcome to)\b",
        lower,
    ):
        return True
    return False
