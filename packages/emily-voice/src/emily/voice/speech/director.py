"""Speech Director — plans spoken delivery without random fillers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from emily.voice.hardware import detect_hardware
from emily.voice.language import LanguageDetector, has_devanagari
from emily.voice.speech.hinglish_tts import prepare_hindi_for_tts
from emily.voice.models import (
    HardwareInfo,
    HardwareProfile,
    LanguageState,
    PauseProfile,
    SpeechPlan,
    VoicePersonality,
)
from emily.voice.personality import DEFAULT_PERSONALITY
from emily.voice.settings_bridge import prefer_lightweight_tts, voice_flag
from emily.voice.speech.prosody import compute_energy, compute_pace, compute_pitch
from emily.voice.speech.segmentation import segment_for_speech
from emily.voice.speech.styles import infer_emotion_from_text, is_expressive, style_from_personality
from emily.voice.tts.registry import TTS_CAPABILITIES


class SpeechDirector:
    """Transforms response text into a SpeechPlan for TTS routing."""

    def __init__(self, *, settings: Any | None = None) -> None:
        self.settings = settings

    def plan(
        self,
        text: str,
        *,
        language_state: LanguageState | None = None,
        personality: VoicePersonality | None = None,
        hardware: HardwareInfo | None = None,
        available_backends: Sequence[str] | None = None,
        emotion: str | None = None,
        settings: Any | None = None,
    ) -> SpeechPlan:
        cfg = settings if settings is not None else self.settings
        persona = personality or DEFAULT_PERSONALITY
        hw = hardware or detect_hardware()
        lang = language_state or LanguageState(dominant=persona.default_language.split("-")[0])

        use_emotion = bool(voice_flag(cfg, "voice_emotion", True))
        use_pacing = bool(voice_flag(cfg, "voice_adaptive_pacing", True))
        use_pauses = bool(voice_flag(cfg, "voice_adaptive_pauses", True))
        use_codeswitch = bool(voice_flag(cfg, "voice_code_switching", True))

        emotion_label = emotion or (infer_emotion_from_text(text) if use_emotion else "neutral")
        style = style_from_personality(persona, emotion=emotion_label if use_emotion else "neutral")
        energy = compute_energy(persona, style) if use_emotion else 0.5
        pace = compute_pace(persona, style) if use_pacing else 1.0
        pitch = compute_pitch(persona, style) if use_emotion else 0.0

        dominant = lang.dominant.split("-")[0].lower()
        secondary = lang.secondary.split("-")[0].lower() if lang.secondary else None
        code_switching = (lang.code_switching or bool(secondary)) if use_codeswitch else False
        if not use_codeswitch:
            secondary = None
        available = set(available_backends or [])

        speak_text = prepare_hindi_for_tts(text.strip(), language=dominant)

        backend = self._prefer_backend(
            text=speak_text,
            dominant=dominant,
            code_switching=code_switching,
            expressive=is_expressive(style, energy=energy) if use_emotion else False,
            hardware=hw,
            available=available,
            settings=cfg,
        )

        voice = persona.voice_name
        if backend == "kokoro" and dominant == "hi":
            voice = "hf_beta"

        pause_profile = PauseProfile.NATURAL if use_pauses else PauseProfile.SHORT
        if hw.profile == HardwareProfile.LOW:
            pause_profile = PauseProfile.SHORT

        segments = segment_for_speech(
            speak_text,
            language=dominant,
            pause_profile=pause_profile,
            code_switching=code_switching,
            secondary_language=secondary,
        )
        return SpeechPlan(
            text=speak_text,
            language=dominant,
            secondary_language=secondary,
            code_switching=code_switching,
            style=style,
            emotion=emotion_label,
            energy=energy,
            pace=pace,
            pitch=pitch,
            pause_profile=pause_profile,
            emphasis=[],
            pronunciation_hints=dict(persona.pronunciation_hints),
            voice=voice,
            tts_backend=backend,
            segments=segments,
        )

    def _prefer_backend(
        self,
        *,
        text: str,
        dominant: str,
        code_switching: bool,
        expressive: bool,
        hardware: HardwareInfo,
        available: set[str],
        settings: Any | None = None,
    ) -> str | None:
        def ok(name: str) -> bool:
            if available and name not in available:
                return False
            return name in TTS_CAPABILITIES

        low = hardware.profile == HardwareProfile.LOW
        default = str(voice_flag(settings, "tts_default", "kokoro") or "kokoro")

        # On LOW: never prefer chatterbox/indicf5 unless only option
        def low_safe(name: str) -> bool:
            if not low:
                return True
            if name in {"chatterbox", "indicf5"}:
                lighter = [n for n in available if n not in {"chatterbox", "indicf5"}] if available else ["kokoro"]
                return not lighter
            return True

        if default and ok(default) and low_safe(default):
            # Still allow language-specific override below when stronger match exists
            pass

        if LanguageDetector.is_indian(dominant):
            # Prefer Voicebox preset sweet-girl voice when the local API is up.
            if ok("voicebox") and low_safe("voicebox"):
                return "voicebox"

            # Hindi/Hinglish → Kokoro hf_beta (needs Devanagari — prepared upstream).
            if dominant == "hi" and ok("kokoro"):
                return "kokoro"

            if default == "voicebox" and ok("kokoro"):
                return "kokoro"

            # IndicF5 refs are Hindi/Marathi-oriented; other Indic scripts → Kokoro (faster, less hang).
            if dominant in {"ta", "te", "kn", "ml", "gu", "pa", "as"} and ok("kokoro"):
                return "kokoro"
            # GPU / medium+ hardware: IndicF5 for natural Hindi/Indic prosody (Devanagari only).
            if (
                dominant == "hi"
                and has_devanagari(text)
                and ok("indicf5")
                and low_safe("indicf5")
                and not prefer_lightweight_tts(settings)
            ):
                return "indicf5"
            # CPU or low-end: Kokoro is fast (accent is less natural for Hindi).
            if ok("kokoro") and (prefer_lightweight_tts(settings) or low):
                return "kokoro"
            if ok("chatterbox") and low_safe("chatterbox"):
                return "chatterbox"
            if ok("indicf5") and low_safe("indicf5"):
                return "indicf5"
            if ok("kokoro"):
                return "kokoro"

        if ok("voicebox") and low_safe("voicebox"):
            return "voicebox"

        if expressive and ok("chatterbox") and not low:
            return "chatterbox"

        if ok(default) and low_safe(default):
            return default
        if ok("kokoro"):
            return "kokoro"
        if ok("chatterbox") and low_safe("chatterbox"):
            return "chatterbox"
        if ok("indicf5") and low_safe("indicf5"):
            return "indicf5"
        # Only heavy option left
        for name in ("voicebox", "kokoro", "chatterbox", "indicf5"):
            if ok(name):
                return name
        if LanguageDetector.is_indian(dominant):
            return "indicf5"
        return default or "kokoro"
