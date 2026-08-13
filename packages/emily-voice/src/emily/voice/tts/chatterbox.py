"""Chatterbox multilingual TTS adapter — lazy load via chatterbox.mtl_tts."""

from __future__ import annotations

from typing import Any

import numpy as np

from emily.voice.errors import BackendUnavailableError, TTSError
from emily.voice.models import AudioChunk, SpeechPlan, TTSCapability
from emily.voice.tts.registry import TTS_CAPABILITIES

# Emily locale → Chatterbox language_id (see chatterbox.mtl_tts.SUPPORTED_LANGUAGES)
_LANG_MAP: dict[str, str] = {
    "en": "en",
    "en-us": "en",
    "en-gb": "en",
    "en-in": "en",
    "hi": "hi",
    "hi-in": "hi",
    "es": "es",
    "fr": "fr",
    "de": "de",
    "it": "it",
    "pt": "pt",
    "ja": "ja",
    "zh": "zh",
    "ko": "ko",
    "ar": "ar",
    "ru": "ru",
    "tr": "tr",
    "nl": "nl",
    "pl": "pl",
    "sv": "sv",
    "he": "he",
    "fi": "fi",
    "cs": "cs",
    "no": "no",
    "vi": "vi",
}


def map_chatterbox_language(language: str) -> str:
    key = (language or "en").lower().strip()
    if key in _LANG_MAP:
        return _LANG_MAP[key]
    base = key.split("-")[0]
    return _LANG_MAP.get(base, "en")


class ChatterboxTTS:
    name = "chatterbox"

    def __init__(self, *, device: str | None = None, sample_rate: int = 24000) -> None:
        self.device = device or "cpu"
        self.sample_rate = sample_rate
        self._model: Any | None = None

    @property
    def capabilities(self) -> TTSCapability:
        return TTS_CAPABILITIES["chatterbox"]

    def available(self) -> bool:
        try:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS  # noqa: F401

            return True
        except Exception:
            try:
                from chatterbox.tts import ChatterboxTTS as _En  # noqa: F401

                return True
            except Exception:
                return False

    async def load(self) -> None:
        if self._model is not None:
            return
        model_cls: Any | None = None
        try:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            model_cls = ChatterboxMultilingualTTS
        except Exception as exc:
            try:
                from chatterbox.tts import ChatterboxTTS as EnglishTTS

                model_cls = EnglishTTS
            except Exception as exc2:
                raise BackendUnavailableError(
                    "chatterbox-tts is not installed; pip install 'emily-voice[chatterbox]' "
                    "(upstream tested on Python 3.11 — use a 3.11 venv if pip fails on 3.12)",
                    backend=self.name,
                    cause=exc2,
                ) from exc
        try:
            if model_cls.__name__ == "ChatterboxMultilingualTTS":
                self._model = model_cls.from_pretrained(device=self.device, t3_model="v3")
            else:
                self._model = model_cls.from_pretrained(device=self.device)
        except TypeError:
            self._model = model_cls.from_pretrained()
        except Exception as exc:
            raise BackendUnavailableError(
                f"failed to load Chatterbox: {exc}",
                backend=self.name,
                cause=exc,
            ) from exc

    async def unload(self) -> None:
        self._model = None

    async def synthesize(self, plan: SpeechPlan) -> AudioChunk:
        await self.load()
        assert self._model is not None
        text = plan.text if not plan.segments else " ".join(s.text for s in plan.segments)
        lang = map_chatterbox_language(plan.language)
        try:
            if hasattr(self._model, "generate"):
                try:
                    audio = self._model.generate(text, language_id=lang)
                except TypeError:
                    audio = self._model.generate(text)
            else:
                audio = self._model(text)
            arr = np.asarray(audio, dtype=np.float32).reshape(-1)
            if hasattr(audio, "detach"):
                arr = audio.detach().cpu().numpy().astype(np.float32).reshape(-1)
            elif hasattr(audio, "numpy") and not isinstance(audio, np.ndarray):
                arr = np.asarray(audio.numpy(), dtype=np.float32).reshape(-1)
            if arr.size == 0:
                raise TTSError("chatterbox produced empty audio", details={"backend": self.name})
            sr = int(getattr(self._model, "sr", self.sample_rate))
            return AudioChunk(
                samples=arr.tolist(),
                sample_rate=sr,
                channels=1,
                backend=self.name,
            )
        except (BackendUnavailableError, TTSError):
            raise
        except Exception as exc:
            raise TTSError(f"chatterbox synthesis failed: {exc}", cause=exc) from exc
