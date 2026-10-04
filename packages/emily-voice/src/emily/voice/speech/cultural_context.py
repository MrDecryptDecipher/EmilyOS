"""Cultural / conversational context for spoken LLM replies."""

from __future__ import annotations

import re

from emily.voice.bangla_hints import looks_like_roman_bangla
from emily.voice.language import latin_letter_share, script_counts

# Playful challenges — user wants personality, not a factual answer.
_PLAYFUL_CHALLENGE = re.compile(
    r"\b("
    r"impress me|surprise me|entertain me|amuse me|make me laugh|"
    r"show me what you'?ve got|show me what you got|do something cool|"
    r"blow my mind|tell me something cool|say something funny|"
    r"kuchh dikhao|kuch dikhao|mojar kichu|hasao|impress karo"
    r")\b",
    re.IGNORECASE,
)

_CULTURAL_GUIDANCE: dict[str, str] = {
    "bn": (
        "Reply in **Bengali script** (বাংলা). Match their playful energy with a short iconic "
        "Bengali film dialogue, meme, or witty one-liner locals would instantly recognize "
        "(e.g. bold Kali-style banter like «মারবো এখানে, লাশ পড়বে শোশানে» when they say "
        "«impress me»). Stay soft Emily at the core — playful, not aggressive or vulgar."
    ),
    "hi": (
        "Reply in **Devanagari**. Match playful energy with a short famous Hindi film line, "
        "Hinglish meme, or desi one-liner — warm and fun, not rude."
    ),
    "ta": (
        "Reply in **Tamil script** with a short well-known Tamil film quip or playful local line."
    ),
    "te": (
        "Reply in **Telugu script** with a short famous Telugu film-style playful line."
    ),
    "en": (
        "Reply in casual English with a witty, surprising one-liner — charming and playful."
    ),
}


def looks_like_playful_challenge(text: str) -> bool:
    return bool(_PLAYFUL_CHALLENGE.search(text or ""))


def infer_reply_language(
    transcript: str,
    *,
    detected: str | None = None,
    session_dominant: str | None = None,
    preferred: str | None = None,
) -> str:
    """
    Pick the language Emily should reply in.

    Uses script in the utterance first, then ASR detect, then sticky session /
    adaptation preference when the user switches to short English (e.g. «impress me»).
    """
    text = (transcript or "").strip()
    if not text:
        base = (preferred or session_dominant or detected or "en").split("-")[0].lower()
        return base if base not in {"", "auto"} else "en"

    counts = script_counts(text)
    for lang in ("bn", "hi", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or"):
        if counts.get(lang, 0) > 0:
            return lang

    if looks_like_roman_bangla(text):
        return "bn"

    det = (detected or "").split("-")[0].lower()
    sess = (session_dominant or "").split("-")[0].lower()
    pref = (preferred or "").split("-")[0].lower()

    if det and det not in {"", "auto", "en"}:
        return det
    if sess and sess not in {"", "auto", "en"}:
        return sess

    # Short English after an Indic session → keep cultural continuity.
    if latin_letter_share(text) >= 0.85 and pref in {"bn", "hi", "ta", "te", "mr", "gu"}:
        words = len(re.findall(r"[a-zA-Z']+", text))
        if words <= 14 or looks_like_playful_challenge(text):
            return pref

    if pref and pref not in {"", "auto"}:
        return pref
    return "en"


def cultural_reply_guidance(transcript: str, reply_language: str) -> str | None:
    """Extra system prompt when the user wants personality / cultural flair."""
    lang = (reply_language or "en").split("-")[0].lower()
    if not looks_like_playful_challenge(transcript):
        return None
    base = _CULTURAL_GUIDANCE.get(lang) or _CULTURAL_GUIDANCE["en"]
    return (
        "The user asked for a playful / impressive moment — NOT a factual answer. "
        f"{base} One or two short sentences max."
    )


def spoken_language_instruction(reply_language: str) -> str:
    """System line telling the LLM which language/script to use."""
    lang = (reply_language or "en").split("-")[0].lower()
    script_notes = {
        "bn": "Bengali script (বাংলা)",
        "hi": "Devanagari Hindi",
        "mr": "Devanagari Marathi",
        "ta": "Tamil script",
        "te": "Telugu script",
        "kn": "Kannada script",
        "ml": "Malayalam script",
        "gu": "Gujarati script",
        "pa": "Gurmukhi Punjabi",
        "or": "Odia script",
        "en": "natural casual English",
        "fr": "French",
        "es": "Spanish",
    }
    label = script_notes.get(lang, lang)
    return (
        f"Reply language for this turn: **{lang}** ({label}). "
        "Use the native script when one exists. "
        "If the user spoke English but your reply language is an Indic language, "
        "they likely want cultural continuity — reply in that language, not English. "
        "Never use Romanized transliteration when a native script is available."
    )
