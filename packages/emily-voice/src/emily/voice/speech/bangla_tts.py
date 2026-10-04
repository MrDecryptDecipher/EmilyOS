"""Prepare Roman Bangla text for TTS (IndicF5 needs Bengali script)."""

from __future__ import annotations

import re

from emily.voice.language import has_bengali

_ROMAN_TO_BENGALI: dict[str, str] = {
    "apni kemon achhen": "আপনি কেমন আছেন",
    "kemon acho": "কেমন আছো",
    "kemon achho": "কেমন আছো",
    "ki khobor": "কি খবর",
    "apnar": "আপনার",
    "apni": "আপনি",
    "tumi": "তুমি",
    "tomar": "তোমার",
    "tomake": "তোমাকে",
    "amar": "আমার",
    "ami": "আমি",
    "kemon": "কেমন",
    "keno": "কেন",
    "kothay": "কোথায়",
    "kotha": "কথা",
    "khobor": "খবর",
    "bhalo": "ভালো",
    "valo": "ভালো",
    "hobe": "হবে",
    "bolchi": "বলছি",
    "bolte": "বলতে",
    "bolo": "বলো",
    "lagche": "লাগছে",
    "lagbe": "লাগবে",
    "dhonnobad": "ধন্যবাদ",
    "nomoshkar": "নমস্কার",
    "nomoskar": "নমস্কার",
    "shubho": "শুভ",
    "ekhon": "এখন",
    "akhon": "এখন",
    "ekhane": "এখানে",
    "onek": "অনেক",
    "khub": "খুব",
    "achhi": "আছি",
    "achi": "আছি",
    "achhe": "আছে",
    "ache": "আছে",
    "parbo": "পারব",
    "parbi": "পারবি",
    "jani": "জানি",
    "janina": "জানি না",
    "shono": "শোনো",
    "kichu": "কিছু",
    "kokhon": "কখন",
    "kivabe": "কীভাবে",
    "kibhabe": "কীভাবে",
    "haan": "হ্যাঁ",
    "na": "না",
    "ar": "আর",
    "to": "তো",
    "ki": "কি",
    "ke": "কে",
}


def roman_bangla_to_bengali(text: str) -> str:
    """Best-effort Roman Bangla → Bengali script for local TTS."""
    cleaned = (text or "").strip()
    if not cleaned or has_bengali(cleaned):
        return cleaned

    out = cleaned
    for roman, beng in sorted(_ROMAN_TO_BENGALI.items(), key=lambda item: -len(item[0])):
        out = re.sub(rf"\b{re.escape(roman)}\b", beng, out, flags=re.IGNORECASE)

    out = re.sub(r"\b[A-Za-z]+\b", "", out)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.])", r"\1", out)
    return out.strip(" ,")


def prepare_bengali_for_tts(text: str, *, language: str | None = None) -> str:
    """Normalize Bengali reply text before synthesis."""
    lang = (language or "en").split("-")[0].lower()
    if lang != "bn":
        return text
    converted = roman_bangla_to_bengali(text)
    return converted or text
