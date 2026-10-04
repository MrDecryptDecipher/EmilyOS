"""BanglaASR — fine-tuned Whisper-small for Bengali (Mozilla Common Voice)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import numpy as np

from emily.voice.audio.processing import ensure_float32_mono, resample
from emily.voice.errors import ASRError, BackendUnavailableError
from emily.voice.hf_compat import ensure_hf_hub_windows_compat
from emily.voice.models import AudioChunk
from emily.voice.settings_bridge import resolve_device, voice_flag

DEFAULT_MODEL_ID = "bangla-speech-processing/BanglaASR"
_TARGET_SR = 16000


class BanglaASR:
    """
    Hugging Face BanglaASR adapter.

    Model: https://huggingface.co/bangla-speech-processing/BanglaASR
    Fine-tuned Whisper-small (~244M) — WER ~4.58% on Bangla Mozilla Common Voice.
    """

    name = "bangla-asr"

    def __init__(
        self,
        *,
        model_id: str | None = None,
        device: str | None = None,
        settings: Any | None = None,
    ) -> None:
        self.settings = settings
        self.model_id = (
            str(voice_flag(settings, "voice_bangla_asr_model", DEFAULT_MODEL_ID) or DEFAULT_MODEL_ID)
            if settings is not None
            else (model_id or DEFAULT_MODEL_ID)
        )
        self.device = device or resolve_device(settings)
        self._model: Any | None = None
        self._processor: Any | None = None
        self.last_detected_language: str | None = "bn"
        self.last_language_probability: float | None = None
        self.last_transcript: str = ""
        self.last_retry_used: bool = False

    def available(self) -> bool:
        if not bool(voice_flag(self.settings, "voice_bangla_asr_enabled", True)):
            return False
        try:
            import torch  # noqa: F401
            from transformers import WhisperForConditionalGeneration, WhisperProcessor  # noqa: F401

            return True
        except Exception:
            return False

    def _torch_device(self) -> str:
        import torch

        if self.device == "cuda" and torch.cuda.is_available():
            return "cuda"
        if self.device == "mps" and getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    async def load(self) -> None:
        if self._model is not None:
            return
        await asyncio.to_thread(self._load_sync)

    def _load_sync(self) -> None:
        if self._model is not None:
            return
        ensure_hf_hub_windows_compat()
        try:
            import torch
            from transformers import WhisperForConditionalGeneration, WhisperProcessor
        except Exception as exc:
            raise BackendUnavailableError(
                "BanglaASR requires transformers and torch; "
                "pip install 'emily-voice[bangla-asr]'",
                backend=self.name,
                cause=exc,
            ) from exc

        device = self._torch_device()
        cache_dir = self._cache_dir()
        kwargs: dict[str, Any] = {}
        if cache_dir is not None:
            kwargs["cache_dir"] = cache_dir

        try:
            self._processor = WhisperProcessor.from_pretrained(self.model_id, **kwargs)
            self._model = WhisperForConditionalGeneration.from_pretrained(
                self.model_id,
                torch_dtype=torch.float32,
                **kwargs,
            )
            self._model = self._model.to(device)
            self._model.eval()
        except Exception as exc:
            raise BackendUnavailableError(
                f"failed to load BanglaASR model {self.model_id}: {exc}",
                backend=self.name,
                cause=exc,
            ) from exc

    def _cache_dir(self) -> str | None:
        if self.settings is None:
            return None
        models_dir = getattr(self.settings, "voice_models_directory", None)
        if not models_dir:
            return None
        root = Path(models_dir) / "hf-cache"
        root.mkdir(parents=True, exist_ok=True)
        return str(root)

    async def unload(self) -> None:
        self._model = None
        self._processor = None
        self.last_detected_language = "bn"
        self.last_language_probability = None
        self.last_transcript = ""
        self.last_retry_used = False

    def _to_pcm16k(self, audio: AudioChunk) -> np.ndarray:
        samples = ensure_float32_mono(audio.samples, channels=audio.channels)
        if audio.sample_rate != _TARGET_SR:
            samples = resample(samples, audio.sample_rate, _TARGET_SR)
        return samples.astype(np.float32, copy=False)

    def transcribe_pcm(self, pcm: np.ndarray) -> tuple[str, str, float]:
        """Sync transcribe float32 mono 16 kHz PCM — used by Whisper retry loop."""
        assert self._model is not None and self._processor is not None
        import torch

        if pcm.size == 0:
            return "", "bn", 0.0

        device = self._torch_device()
        feature_extractor = self._processor.feature_extractor
        input_features = feature_extractor(
            pcm,
            sampling_rate=_TARGET_SR,
            return_tensors="pt",
        ).input_features
        input_features = input_features.to(device)

        with torch.no_grad():
            predicted_ids = self._model.generate(inputs=input_features)[0]

        text = self._processor.decode(predicted_ids, skip_special_tokens=True).strip()
        return text, "bn", 0.92 if text else 0.0

    async def transcribe(
        self,
        audio: AudioChunk,
        *,
        language: str | None = None,
        language_hint: str | None = None,
        on_status: Any | None = None,
        **_: Any,
    ) -> str:
        if on_status is not None:
            on_status("Transcribing (BanglaASR — Bengali)...")
        await self.load()
        pcm = self._to_pcm16k(audio)
        try:
            text, detected, prob = await asyncio.to_thread(self.transcribe_pcm, pcm)
        except Exception as exc:
            raise ASRError(f"BanglaASR failed: {exc}", cause=exc) from exc
        self.last_detected_language = detected
        self.last_language_probability = prob
        self.last_transcript = text
        self.last_retry_used = False
        return text

    async def transcribe_stream(self, audio: AudioChunk, **kwargs: Any) -> AsyncIterator[str]:
        text = await self.transcribe(audio, **kwargs)
        if text:
            yield text
