"""IndicF5 reference audio defaults (from AI4Bharat/IndicF5 prompts)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_REF_BASE = "https://raw.githubusercontent.com/AI4Bharat/IndicF5/main/prompts"

# Legacy bundled default (Punjabi — fine for pa, foreign-sounding for Hindi).
DEFAULT_REF_FILENAME = "PAN_F_HAPPY_00001.wav"
DEFAULT_REF_URL = f"{_REF_BASE}/{DEFAULT_REF_FILENAME}"
DEFAULT_REF_TEXT = (
    "ਭਹੰਪੀ ਵਿੱਚ ਸਮਾਰਕਾਂ ਦੇ ਭਵਨ ਨਿਰਮਾਣ ਕਲਾ ਦੇ ਵੇਰਵੇ ਗੁੰਝਲਦਾਰ ਅਤੇ ਹੈਰਾਨ ਕਰਨ ਵਾਲੇ ਹਨ, "
    "ਜੋ ਮੈਨੂੰ ਖੁਸ਼ ਕਰਦੇ ਹਨ।"
)

# Per-language prompt presets from upstream IndicF5 prompts/.
# We now use perfect native accents generated via edge-tts.
LANGUAGE_REF_PRESETS: dict[str, tuple[str, str]] = {
    "hi": (
        "hi_ref.wav",
        "नमस्ते! मैं एमिली हूँ। मैं आपकी कैसे मदद कर सकती हूँ?",
    ),
    "mr": (
        "hi_ref.wav",
        "नमस्ते! मैं एमिली हूँ। मैं आपकी कैसे मदद कर सकती हूँ?",
    ),
    "bn": (
        "bn_ref.wav",
        "নমস্কার! আমি এমিলি। আমি আপনাকে কীভাবে সাহায্য করতে পারি?",
    ),
    "te": (
        "te_ref.wav",
        "నమస్కారం! నేను ఎమిలీని. నేను మీకు ఎలా సహాయపడగలను?",
    ),
    "or": (
        "bn_ref.wav",  # Eastern Indo-Aryan fallback for Odia (much better than Punjabi)
        "নমস্কার! আমি এমিলি। আমি আপনাকে কীভাবে সাহায্য করতে পারি?",
    ),
    "pa": (DEFAULT_REF_FILENAME, DEFAULT_REF_TEXT),
    "ta": (DEFAULT_REF_FILENAME, DEFAULT_REF_TEXT),
    "kn": (DEFAULT_REF_FILENAME, DEFAULT_REF_TEXT),
    "gu": (DEFAULT_REF_FILENAME, DEFAULT_REF_TEXT),
    "as": (
        "bn_ref.wav",
        "নমস্কার! আমি এমিলি। আমি আপনাকে কীভাবে সাহায্য করতে পারি?",
    ),
}

# Languages that should prefer the Devanagari (Marathi) reference voice.
_DEVANAGARI_LANGS = frozenset({"hi", "mr", "sa", "ne", "en"})


def default_ref_dir(settings: Any | None = None) -> Path:
    if settings is not None:
        voice_dir = getattr(settings, "voice_directory", None)
        if voice_dir:
            return Path(voice_dir) / "indicf5_ref"
    return Path("data/voice/indicf5_ref")


def _language_preset(language: str | None) -> tuple[str, str] | None:
    if not language:
        return None
    base = language.split("-")[0].lower().strip()
    if base in LANGUAGE_REF_PRESETS:
        return LANGUAGE_REF_PRESETS[base]
    if base in _DEVANAGARI_LANGS:
        return LANGUAGE_REF_PRESETS["hi"]
    return None


def resolve_indicf5_ref(
    settings: Any | None,
    *,
    language: str | None = None,
    ref_audio_path: Path | str | None = None,
    ref_text: str | None = None,
) -> tuple[Path | None, str]:
    """Resolve IndicF5 reference audio + transcript for a target language."""
    audio = ref_audio_path
    if audio is None and settings is not None:
        configured = getattr(settings, "voice_indicf5_ref_audio", None)
        if configured:
            audio = Path(str(configured))
    text = ref_text or ""
    if not text and settings is not None:
        text = str(getattr(settings, "voice_indicf5_ref_text", "") or "")

    if audio is not None:
        path = Path(audio)
        if path.is_file():
            return path, text or _fallback_ref_text(language)

    preset = _language_preset(language)
    ref_dir = default_ref_dir(settings)
    if preset is not None:
        filename, preset_text = preset
        bundled = ref_dir / filename
        if bundled.is_file():
            return bundled, text or preset_text

    bundled = ref_dir / DEFAULT_REF_FILENAME
    if bundled.is_file():
        return bundled, text or DEFAULT_REF_TEXT
    return None, text or _fallback_ref_text(language)


def _fallback_ref_text(language: str | None) -> str:
    preset = _language_preset(language)
    if preset is not None:
        return preset[1]
    return DEFAULT_REF_TEXT


def download_ref_file(filename: str, target_dir: Path | str) -> Path:
    import urllib.request

    root = Path(target_dir)
    root.mkdir(parents=True, exist_ok=True)
    dest = root / filename
    if not dest.is_file() or dest.stat().st_size < 1000:
        urllib.request.urlretrieve(f"{_REF_BASE}/{filename}", dest)  # noqa: S310
    return dest


def download_default_ref(target_dir: Path | str) -> Path:
    """Download Hindi-friendly + legacy reference WAVs (explicit opt-in from ModelManager)."""
    root = Path(target_dir)
    root.mkdir(parents=True, exist_ok=True)
    # Hindi/Hinglish: calm wiki-style Marathi female (sweeter than HAPPY prompts).
    download_ref_file("MAR_F_WIKI_00001.wav", root)
    download_ref_file("MAR_F_HAPPY_00001.wav", root)
    download_ref_file(DEFAULT_REF_FILENAME, root)
    meta = root / "ref.json"
    hi_filename, hi_text = LANGUAGE_REF_PRESETS["hi"]
    meta.write_text(
        (
            "{\n"
            f'  "hindi_default": "{hi_filename}",\n'
            f'  "hindi_ref_text": {hi_text!r},\n'
            f'  "legacy_default": "{DEFAULT_REF_FILENAME}"\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    return root / hi_filename
