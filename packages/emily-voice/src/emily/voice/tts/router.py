"""TTS backend selection with fallback chain."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from emily.voice.errors import BackendUnavailableError
from emily.voice.hardware import detect_hardware
from emily.voice.language import LanguageDetector, has_devanagari
from emily.voice.models import HardwareProfile, SpeechPlan, TTSCapability
from emily.voice.settings_bridge import prefer_lightweight_tts, voice_flag
from emily.voice.speech.styles import is_expressive
from emily.voice.tts.base import TTSEngine
from emily.voice.tts.registry import TTS_CAPABILITIES


def _lang_supported(cap: TTSCapability, lang: str) -> bool:
    base = lang.split("-")[0].lower()
    return base in {x.lower() for x in cap.languages} or lang.lower() in {x.lower() for x in cap.languages}


def score_backend(
    name: str,
    plan: SpeechPlan,
    *,
    available: bool,
    capability: TTSCapability | None = None,
    settings: Any | None = None,
    hardware_profile: HardwareProfile | None = None,
) -> float:
    if not available:
        return -1e9
    cap = capability or TTS_CAPABILITIES.get(name)
    if cap is None:
        return -1e6
    score = 100.0 - float(cap.priority) * 10.0
    lang = plan.language.split("-")[0].lower()
    if _lang_supported(cap, lang):
        score += 40.0
    else:
        score -= 30.0
    if plan.tts_backend == name:
        score += 50.0
    default = str(voice_flag(settings, "tts_default", "") or "")
    if default and default == name:
        score += 45.0
    if LanguageDetector.is_indian(lang) and name == "indicf5" and not prefer_lightweight_tts(settings):
        score += 35.0
    if name == "voicebox":
        score += 55.0
    # When Voicebox is the configured default, Kokoro is the calm fallback — not IndicF5.
    if default == "voicebox":
        if name == "kokoro" and lang == "hi":
            score += 40.0
        if name == "indicf5" and lang == "hi" and not has_devanagari(plan.text):
            score -= 120.0
    if is_expressive(plan.style, energy=plan.energy) and cap.expressive:
        score += 25.0
    if cap.lightweight:
        score += 8.0
    if plan.code_switching and cap.multilingual:
        score += 5.0
    # CPU: Kokoro is ~100x faster than IndicF5; avoid multi-minute hangs and bad CPU synth.
    if prefer_lightweight_tts(settings) and name in {"chatterbox", "indicf5"}:
        score -= 120.0
    # LOW hardware: never prefer heavy backends unless they are the only option
    profile = hardware_profile
    if profile is None:
        try:
            profile = detect_hardware().profile
        except Exception:
            profile = None
    if profile == HardwareProfile.LOW and name in {"chatterbox", "indicf5"}:
        score -= 80.0
    return score


def fallback_chain(
    plan: SpeechPlan,
    *,
    available_names: Sequence[str],
    settings: Any | None = None,
) -> list[str]:
    available = list(available_names)
    try:
        profile = detect_hardware().profile
    except Exception:
        profile = None
    ranked = sorted(
        available,
        key=lambda n: score_backend(
            n, plan, available=True, settings=settings, hardware_profile=profile
        ),
        reverse=True,
    )
    # Consistency: if plan already picked a backend and it is available, pin first
    if plan.tts_backend and plan.tts_backend in ranked:
        # On LOW, do not pin heavy backends ahead of lighter ones when alternatives exist
        heavy = plan.tts_backend in {"chatterbox", "indicf5"}
        if not (profile == HardwareProfile.LOW and heavy and any(x == "kokoro" for x in ranked)):
            ranked = [plan.tts_backend] + [n for n in ranked if n != plan.tts_backend]
    default = str(voice_flag(settings, "tts_default", "") or "")
    if default and default in ranked:
        # Prefer configured default when available (unless plan pin already applied)
        if not plan.tts_backend or plan.tts_backend not in ranked:
            ranked = [default] + [n for n in ranked if n != default]
        elif plan.tts_backend == default:
            pass
        elif profile != HardwareProfile.LOW or default == "kokoro":
            # Soft prefer default after plan backend
            rest = [n for n in ranked if n not in {plan.tts_backend, default}]
            ranked = [plan.tts_backend, default, *rest]
    return ranked


def select_tts_backend(
    plan: SpeechPlan,
    engines: Mapping[str, TTSEngine] | Sequence[TTSEngine],
    *,
    pinned: str | None = None,
    settings: Any | None = None,
) -> str:
    """Select a backend for this response; honor pin for consistency within one turn."""
    if isinstance(engines, Mapping):
        engine_map = dict(engines)
    else:
        engine_map = {e.name: e for e in engines}

    available = [name for name, eng in engine_map.items() if eng.available()]
    if pinned and pinned in available:
        return pinned
    chain = fallback_chain(plan, available_names=available, settings=settings)
    if not chain:
        raise BackendUnavailableError(
            "no TTS backends available",
            backend=plan.tts_backend,
            details={"requested": plan.tts_backend, "available": []},
        )
    return chain[0]
