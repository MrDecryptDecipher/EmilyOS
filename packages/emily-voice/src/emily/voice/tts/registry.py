"""Verified TTS capability registry."""

from __future__ import annotations

from emily.voice.models import TTSCapability

# Kokoro language codes (a/b/e/f/h/i/j/p/z) plus ISO aliases we map to them.
KOKORO_LANG_CODES = ("a", "b", "e", "f", "h", "i", "j", "p", "z", "en", "hi")

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
        priority=0,
        expressive=True,
        multilingual=True,
        notes="jamiepine/voicebox local API — clone a sweet young-girl voice in the app.",
    ),
}


def capability_for(name: str) -> TTSCapability | None:
    return TTS_CAPABILITIES.get(name)
