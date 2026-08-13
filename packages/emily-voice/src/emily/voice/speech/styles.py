"""Speech style mapping from personality and emotion cues."""

from __future__ import annotations

from emily.voice.models import SpeechStyle, VoicePersonality

_EMOTION_TO_STYLE: dict[str, SpeechStyle] = {
    "neutral": SpeechStyle.NEUTRAL,
    "happy": SpeechStyle.FRIENDLY,
    "excited": SpeechStyle.EXCITED,
    "sad": SpeechStyle.EMPATHETIC,
    "concerned": SpeechStyle.CONCERNED,
    "calm": SpeechStyle.CALM,
    "technical": SpeechStyle.TECHNICAL,
    "professional": SpeechStyle.PROFESSIONAL,
    "warm": SpeechStyle.WARM,
    "casual": SpeechStyle.CASUAL,
    "empathetic": SpeechStyle.EMPATHETIC,
}


def style_from_personality(personality: VoicePersonality, *, emotion: str | None = None) -> SpeechStyle:
    if emotion:
        mapped = _EMOTION_TO_STYLE.get(emotion.lower().strip())
        if mapped is not None:
            return mapped
    if personality.formality >= 0.7:
        return SpeechStyle.PROFESSIONAL
    if personality.expressiveness >= 0.75 and personality.energy >= 0.7:
        return SpeechStyle.EXCITED
    if personality.energy >= 0.65 and personality.warmth >= 0.6:
        return SpeechStyle.FRIENDLY
    if personality.warmth >= 0.65:
        return SpeechStyle.WARM
    if personality.formality <= 0.3:
        return SpeechStyle.CASUAL
    return personality.default_style


def infer_emotion_from_text(text: str) -> str:
    lowered = text.lower()
    if any(tok in lowered for tok in ("wow", "amazing", "excited", "great news", "yay")):
        return "excited"
    if any(tok in lowered for tok in ("sorry", "unfortunately", "worried", "concern")):
        return "concerned"
    if any(tok in lowered for tok in ("thanks", "thank you", "glad", "happy", "love", "fun")):
        return "warm"
    if any(tok in lowered for tok in ("step", "function", "api", "parameter", "config")):
        return "technical"
    # Default: soft warm — sweet young girl, not hyper/panicky.
    return "warm"


def is_expressive(style: SpeechStyle, *, energy: float) -> bool:
    return (
        style in {SpeechStyle.EXCITED, SpeechStyle.FRIENDLY, SpeechStyle.EMPATHETIC, SpeechStyle.CONCERNED}
        or energy >= 0.75
    )
