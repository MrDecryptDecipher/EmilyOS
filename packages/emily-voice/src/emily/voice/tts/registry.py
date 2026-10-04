"""Verified TTS capability registry."""

from __future__ import annotations

from emily.voice.models import TTSCapability

# Kokoro pipeline codes — NOT all ISO langs (no Bengali, Tamil, Telugu, etc.).
KOKORO_LANG_CODES = ("a", "b", "e", "f", "h", "i", "j", "p", "z", "en", "hi")
KOKORO_SUPPORTED_ISO = frozenset({"en", "es", "fr", "it", "pt", "ja", "zh", "hi", "mr"})

# Languages Kokoro cannot speak — need IndicF5 / Voicebox / Chatterbox.
INDIC_SCRIPT_TTS_LANGS = frozenset({"as", "bn", "gu", "kn", "ml", "mr", "or", "pa", "ta", "te"})


def kokoro_supports(language: str) -> bool:
    base = (language or "en").split("-")[0].lower()
    return base in KOKORO_SUPPORTED_ISO


def language_requires_indicf5(language: str) -> bool:
    """True when Kokoro will produce gibberish and IndicF5 (or similar) is required."""
    base = (language or "en").split("-")[0].lower()
    return base in INDIC_SCRIPT_TTS_LANGS


def backend_supports_language(backend: str, language: str) -> bool:
    cap = TTS_CAPABILITIES.get(backend)
    if cap is None:
        return False
    base = (language or "en").split("-")[0].lower()
    if backend == "kokoro":
        return kokoro_supports(base)
    return base in {x.lower() for x in cap.languages} or language.lower() in {
        x.lower() for x in cap.languages
    }

TTS_CAPABILITIES: dict[str, TTSCapability] = {
    "kokoro": TTSCapability(
        name="kokoro",
        languages=list(KOKORO_LANG_CODES),
        streaming=True,
        lightweight=True,
        priority=1,
        expressive=False,
        multilingual=True,
        notes="Default lightweight TTS; maps ISO langs to kokoro codes.",
    ),
    "indicf5": TTSCapability(
        name="indicf5",
        languages=["as", "bn", "gu", "hi", "kn", "ml", "mr", "or", "pa", "ta", "te"],
        streaming=False,
        lightweight=False,
        priority=2,
        expressive=False,
        multilingual=True,
        notes="Indic TTS via IndicF5 (git install). Requires reference audio.",
    ),
    "chatterbox": TTSCapability(
        name="chatterbox",
        languages=[
            "ar",
            "da",
            "de",
            "el",
            "en",
            "es",
            "fi",
            "fr",
            "he",
            "hi",
            "it",
            "ja",
            "ko",
            "ms",
            "nl",
            "no",
            "pl",
            "pt",
            "ru",
            "sv",
            "sw",
            "tr",
            "zh",
        ],
        streaming=False,
        lightweight=False,
        priority=3,
        expressive=True,
        multilingual=True,
        notes="Expressive multilingual TTS (chatterbox-tts).",
    ),
    "voicebox": TTSCapability(
        name="voicebox",
        languages=[
            "ar", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "it", 
            "ja", "ko", "ms", "nl", "no", "pl", "pt", "ru", "sv", "sw", "tr", "zh"
        ],
        streaming=False,
        lightweight=False,
        priority=4,
        expressive=True,
        multilingual=True,
        notes="REST adapter for Voicebox desktop GUI.",
    ),
}


def capability_for(name: str) -> TTSCapability | None:
    return TTS_CAPABILITIES.get(name)
