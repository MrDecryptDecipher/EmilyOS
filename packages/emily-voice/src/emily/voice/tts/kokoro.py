"""Kokoro TTS adapter — lazy import of kokoro.KPipeline."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import numpy as np

from emily.voice.errors import BackendUnavailableError, TTSError
from emily.voice.language import has_devanagari
from emily.voice.models import AudioChunk, SpeechPlan, TTSCapability
from emily.voice.tts.registry import TTS_CAPABILITIES

# ISO / Emily language → Kokoro pipeline lang code
_LANG_MAP: dict[str, str] = {
    "en": "a",
    "en-us": "a",
    "en-gb": "b",
    "en-in": "a",
    "a": "a",
    "b": "b",
    "hi": "h",
    "h": "h",
    "es": "e",
    "e": "e",
    "fr": "f",
    "f": "f",
    "it": "i",
    "i": "i",
    "pt": "p",
    "p": "p",
    "ja": "j",
    "j": "j",
    "zh": "z",
    "z": "z",
}


class KokoroTTS:
    name = "kokoro"

    def __init__(self, *, voice: str | None = None, sample_rate: int = 24000) -> None:
        # af_bella — bright young female; sweeter and more youthful than af_heart.
        self.voice = voice or "af_bella"
        self.sample_rate = sample_rate
        self._pipeline: Any | None = None
        self._lang: str | None = None

    @property
    def capabilities(self) -> TTSCapability:
        return TTS_CAPABILITIES["kokoro"]

    def available(self) -> bool:
        try:
            from kokoro import KPipeline  # noqa: F401

            return True
        except Exception:
            return False

    def _map_lang(self, language: str) -> str:
        key = language.lower()
        if key in _LANG_MAP:
            return _LANG_MAP[key]
        base = key.split("-")[0]
        return _LANG_MAP.get(base, "a")

    async def load(self, *, language: str = "en") -> None:
        if not self.available():
            raise BackendUnavailableError(
                "kokoro is not installed; pip install 'emily-voice[kokoro]'",
                backend=self.name,
            )
        lang = self._map_lang(language)
        if self._pipeline is not None and self._lang == lang:
            return
        self._pipeline = await asyncio.to_thread(self._create_pipeline, lang)
        self._lang = lang

    def _create_pipeline(self, lang: str) -> Any:
        from kokoro import KPipeline

        return KPipeline(lang_code=lang)

    async def unload(self) -> None:
        self._pipeline = None
        self._lang = None

    async def synthesize(self, plan: SpeechPlan) -> AudioChunk:
        chunks: list[np.ndarray] = []
        async for chunk in self.synthesize_stream(plan):
            samples = chunk.samples
            if isinstance(samples, bytes):
                arr = np.frombuffer(samples, dtype=np.float32)
            else:
                arr = np.asarray(samples, dtype=np.float32)
            if arr.size:
                chunks.append(arr)
        if not chunks:
            raise TTSError("kokoro produced empty audio", details={"backend": self.name})
        audio = np.concatenate(chunks)
        return AudioChunk(
            samples=audio.astype(np.float32).tolist(),
            sample_rate=self.sample_rate,
            channels=1,
            backend=self.name,
        )

    async def _ensure_pipeline(self, pipe_lang: str) -> None:
        if self._pipeline is not None and self._lang == pipe_lang:
            return
        self._pipeline = await asyncio.to_thread(self._create_pipeline, pipe_lang)
        self._lang = pipe_lang

    async def synthesize_stream(self, plan: SpeechPlan) -> AsyncIterator[AudioChunk]:
        base_lang = (plan.language or "en").split("-")[0].lower()
        speed = max(0.84, min(0.94, float(plan.pace or 0.86)))
        segment_items = (
            [(s.text, (s.language or plan.language or "en").split("-")[0].lower()) for s in plan.segments]
            if plan.segments
            else [(plan.text, base_lang)]
        )
        try:
            for text, seg_lang in segment_items:
                if not text.strip():
                    continue
                # Kokoro Hindi G2P requires Devanagari — Latin Hinglish sounds wrong.
                if seg_lang == "hi" and not has_devanagari(text):
                    # Latin left after prep — English pipeline (intelligible) beats broken Hindi G2P.
                    pipe_lang = "a"
                    voice = self.voice
                elif seg_lang == "hi":
                    pipe_lang = "h"
                    voice = "hf_beta"
                else:
                    pipe_lang = self._map_lang(seg_lang)
                    voice = plan.voice if plan.voice and not str(plan.voice).startswith("emily") else self.voice
                    if str(voice).startswith("emily") or voice in {"indicf5-hi"}:
                        voice = self.voice
                await self._ensure_pipeline(pipe_lang)
                assert self._pipeline is not None
                for item in self._pipeline(text, voice=voice, speed=speed):
                    arr = self._extract_audio(item)
                    if arr.size == 0:
                        continue
                    yield AudioChunk(
                        samples=arr.tolist(),
                        sample_rate=self.sample_rate,
                        channels=1,
                        backend=self.name,
                    )
        except (BackendUnavailableError, TTSError):
            raise
        except Exception as exc:
            raise TTSError(f"kokoro synthesis failed: {exc}", cause=exc) from exc

    @staticmethod
    def _extract_audio(item: Any) -> np.ndarray:
        """Normalize Kokoro Result / tuple / tensor / ndarray into float32 mono."""
        audio: Any = item
        if hasattr(item, "audio"):
            audio = item.audio
        elif isinstance(item, (tuple, list)) and len(item) >= 3:
            audio = item[2]
        if hasattr(audio, "detach"):
            audio = audio.detach().cpu().numpy()
        elif hasattr(audio, "numpy") and not isinstance(audio, np.ndarray):
            audio = audio.numpy()
        arr = np.asarray(audio, dtype=np.float32)
        return arr.reshape(-1)
