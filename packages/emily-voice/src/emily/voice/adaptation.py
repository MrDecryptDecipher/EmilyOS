"""Per-user voice adaptation profile (pacing / formality / interrupt habits)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from emily.voice.bangla_hints import looks_like_roman_bangla
from emily.voice.models import VoicePersonality


class UserAdaptationProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    formal_casual: float = Field(default=0.5, ge=0.0, le=1.0)
    avg_response_chars: float = 0.0
    speaking_rate_bias: float = 0.0
    code_switch_rate: float = 0.0
    interrupt_count: int = 0
    preferred_language: str | None = None
    preferred_verbosity: float = Field(default=0.5, ge=0.0, le=1.0)
    turn_count: int = 0


_CASUAL_HINTS = re.compile(
    r"\b(hey|yeah|yep|nah|gonna|wanna|lol|haha|yaar|bhai|ok|okay)\b",
    re.IGNORECASE,
)
_FORMAL_HINTS = re.compile(
    r"\b(please|kindly|regarding|therefore|would you|could you|sir|madam)\b",
    re.IGNORECASE,
)
_CODE_SWITCH = re.compile(r"[\u0900-\u097F\u0980-\u09FF\u0A00-\u0A7F\u0A80-\u0AFF"
                          r"\u0B00-\u0B7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F]")


def default_adaptation_path(settings: Any | None = None) -> Path:
    if settings is not None:
        data_dir = getattr(settings, "voice_directory", None)
        if data_dir:
            return Path(data_dir) / "adaptation.json"
    return Path("data/voice/adaptation.json")


def load_adaptation(
    path: Path | str | None = None,
    *,
    settings: Any | None = None,
) -> UserAdaptationProfile:
    target = Path(path) if path is not None else default_adaptation_path(settings)
    if not target.exists():
        return UserAdaptationProfile()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return UserAdaptationProfile.model_validate(raw)
    except Exception:
        pass
    return UserAdaptationProfile()


def save_adaptation(
    profile: UserAdaptationProfile,
    path: Path | str | None = None,
    *,
    settings: Any | None = None,
) -> Path:
    target = Path(path) if path is not None else default_adaptation_path(settings)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return target


class UserAdaptation:
    """Observe turns and adjust personality copy for pacing / formality."""

    def __init__(
        self,
        profile: UserAdaptationProfile | None = None,
        *,
        settings: Any | None = None,
        path: Path | str | None = None,
    ) -> None:
        self.settings = settings
        self.path = Path(path) if path is not None else default_adaptation_path(settings)
        self.profile = profile or load_adaptation(self.path, settings=settings)

    def observe_user_turn(self, transcript: str) -> None:
        text = (transcript or "").strip()
        if not text:
            return
        p = self.profile
        n = p.turn_count
        p.avg_response_chars = (p.avg_response_chars * n + len(text)) / (n + 1) if n else float(len(text))
        casual = 1.0 if _CASUAL_HINTS.search(text) else 0.0
        formal = 1.0 if _FORMAL_HINTS.search(text) else 0.0
        target = 0.5
        if casual and not formal:
            target = 0.75
        elif formal and not casual:
            target = 0.25
        p.formal_casual = p.formal_casual * 0.85 + target * 0.15
        switched = 1.0 if _CODE_SWITCH.search(text) else 0.0
        p.code_switch_rate = p.code_switch_rate * 0.85 + switched * 0.15
        # Infer preferred language from Indic script or strong roman cues.
        if switched:
            indic_chars = len(_CODE_SWITCH.findall(text))
            if indic_chars >= 8:
                if re.search(r"[\u0C00-\u0C7F]", text):
                    p.preferred_language = "te"
                elif re.search(r"[\u0980-\u09FF]", text):
                    p.preferred_language = "bn"
                elif re.search(r"[\u0900-\u097F]", text):
                    p.preferred_language = "hi"
                elif re.search(r"[\u0B00-\u0B7F]", text):
                    p.preferred_language = "or"
                elif re.search(r"[\u0B80-\u0BFF]", text):
                    p.preferred_language = "ta"
        elif looks_like_roman_bangla(text) and len(text) >= 10:
            p.preferred_language = "bn"
        # Longer user turns → slightly slower Emily speaking rate bias
        if len(text) > 160:
            p.speaking_rate_bias = max(-0.08, p.speaking_rate_bias - 0.01)
            p.preferred_verbosity = min(1.0, p.preferred_verbosity + 0.02)
        elif len(text) < 40:
            p.speaking_rate_bias = min(0.06, p.speaking_rate_bias + 0.01)
            p.preferred_verbosity = max(0.0, p.preferred_verbosity - 0.02)
        p.turn_count = n + 1
        self._persist()

    def observe_interrupt(self) -> None:
        self.profile.interrupt_count += 1
        # Frequent interrupts → speak a bit faster / shorter
        self.profile.speaking_rate_bias = min(0.08, self.profile.speaking_rate_bias + 0.02)
        self.profile.preferred_verbosity = max(0.0, self.profile.preferred_verbosity - 0.04)
        self._persist()

    def observe_reply(self, text: str) -> None:
        # Track Emily reply length for verbosity preference smoothing
        reply = (text or "").strip()
        if not reply:
            return
        target = min(1.0, len(reply) / 280.0)
        self.profile.preferred_verbosity = self.profile.preferred_verbosity * 0.9 + target * 0.1
        self._persist()

    def apply_to_personality(self, personality: VoicePersonality) -> VoicePersonality:
        p = self.profile
        formality = max(0.0, min(1.0, 1.0 - p.formal_casual))
        rate = max(0.88, min(1.12, personality.speaking_rate + p.speaking_rate_bias))
        energy = personality.energy
        if p.interrupt_count > 3:
            energy = min(0.95, energy + 0.02)
        # Do not override default_language from a sticky preferred_language —
        # turn-level ASR detection should drive language; sticky lang caused Tamil lock-in.
        return personality.model_copy(
            update={
                "formality": formality * 0.6 + personality.formality * 0.4,
                "speaking_rate": rate,
                "energy": energy,
            }
        )

    def _persist(self) -> None:
        try:
            save_adaptation(self.profile, self.path, settings=self.settings)
        except Exception:
            pass
