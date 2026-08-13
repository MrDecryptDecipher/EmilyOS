"""Prepare Hindi/Hinglish text for TTS (Kokoro hi pipeline needs Devanagari)."""

from __future__ import annotations

import re

from emily.voice.language import has_devanagari

# Common spoken Hinglish → Devanagari (longest keys matched first).
_ROMAN_TO_DEVANAGARI: dict[str, str] = {
    "aapke": "आपके",
    "aapka": "आपका",
    "aapki": "आपकी",
    "aapko": "आपको",
    "aapse": "आपसे",
    "tumhe": "तुम्हें",
    "tumhara": "तुम्हारा",
    "tumhari": "तुम्हारी",
    "mujhe": "मुझे",
    "mujhse": "मुझसे",
    "mera": "मेरा",
    "meri": "मेरी",
    "mere": "मेरे",
    "karna": "करना",
    "karo": "करो",
    "karti": "करती",
    "karta": "करता",
    "karte": "करते",
    "karke": "करके",
    "rahi": "रही",
    "raha": "रहा",
    "rahe": "रहे",
    "yahin": "यहीं",
    "yahan": "यहाँ",
    "wahan": "वहाँ",
    "theek": "ठीक",
    "thik": "ठीक",
    "accha": "अच्छा",
    "acha": "अच्छा",
    "nahi": "नहीं",
    "nahin": "नहीं",
    "haan": "हाँ",
    "han": "हाँ",
    "hoon": "हूँ",
    "hun": "हूँ",
    "hai": "है",
    "hain": "हैं",
    "ho": "हो",
    "bas": "बस",
    "main": "मैं",
    "mein": "मैं",
    "aap": "आप",
    "tum": "तुम",
    "kya": "क्या",
    "kyun": "क्यों",
    "kyu": "क्यू",
    "kaise": "कैसे",
    "kaisa": "कैसा",
    "baat": "बात",
    "kar": "कर",
    "se": "से",
    "par": "पर",
    "me": "में",
    "ko": "को",
    "ka": "का",
    "ki": "की",
    "ke": "के",
    "aur": "और",
    "ya": "या",
    "ji": "जी",
    "na": "ना",
    "hi": "ही",
    "bhi": "भी",
    "abhi": "अभी",
    "yeh": "ये",
    "ye": "ये",
    "woh": "वो",
    "wo": "वो",
    "chat": "चैट",
    "madad": "मदद",
    "dhanyavaad": "धन्यवाद",
    "shukriya": "शुक्रिया",
    "namaste": "नमस्ते",
}


def roman_hinglish_to_devanagari(text: str) -> str:
    """
    Best-effort Roman Hinglish → Devanagari for local TTS.

    IndicF5 and Kokoro Hindi both need Indic script; Latin letters produce
    gibberish or phonemizer errors.
    """
    cleaned = (text or "").strip()
    if not cleaned or has_devanagari(cleaned):
        return cleaned

    out = cleaned
    for roman, dev in sorted(_ROMAN_TO_DEVANAGARI.items(), key=lambda item: -len(item[0])):
        out = re.sub(rf"\b{re.escape(roman)}\b", dev, out, flags=re.IGNORECASE)

    # Drop stray Latin words Kokoro Hindi cannot pronounce cleanly.
    out = re.sub(r"\b[A-Za-z]+\b", "", out)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.])", r"\1", out)
    return out.strip(" ,")


def prepare_hindi_for_tts(text: str, *, language: str | None = None) -> str:
    """Normalize Hindi reply text before synthesis."""
    lang = (language or "en").split("-")[0].lower()
    if lang != "hi":
        return text
    converted = roman_hinglish_to_devanagari(text)
    return converted or text
