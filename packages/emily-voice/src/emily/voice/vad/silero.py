"""VAD: Silero when available, else real energy-threshold fallback."""

from __future__ import annotations

from typing import Any

import numpy as np

from emily.voice.audio.processing import ensure_float32_mono
from emily.voice.models import AudioChunk


class EnergyVAD:
    """
    Real energy-threshold VAD (not a fake/simulated detector).

    Uses RMS energy against a configurable threshold. Documented as the
    fallback when torch + Silero are unavailable.
    """

    name = "energy"

    def __init__(self, *, threshold: float = 0.015, min_speech_ms: float = 120.0) -> None:
        self.threshold = threshold
        self.min_speech_ms = min_speech_ms

    def available(self) -> bool:
        return True

    def is_speech_frame(self, audio: AudioChunk) -> bool:
        """Energy-only check suitable for short VAD frames."""
        samples = ensure_float32_mono(audio.samples, channels=audio.channels)
        if samples.size == 0:
            return False
        rms = float(np.sqrt(np.mean(np.square(samples))))
        return rms >= self.threshold

    def is_speech(self, audio: AudioChunk) -> bool:
        samples = ensure_float32_mono(audio.samples, channels=audio.channels)
        if samples.size == 0:
            return False
        rms = float(np.sqrt(np.mean(np.square(samples))))
        duration_ms = (samples.size / max(audio.sample_rate, 1)) * 1000.0
        if duration_ms < self.min_speech_ms:
            # Short frames: energy only (used by continuous VAD listen)
            return rms >= self.threshold
        return rms >= self.threshold

    def speech_probability(self, audio: AudioChunk) -> float:
        samples = ensure_float32_mono(audio.samples, channels=audio.channels)
        if samples.size == 0:
            return 0.0
        rms = float(np.sqrt(np.mean(np.square(samples))))
        return float(min(1.0, rms / max(self.threshold, 1e-6)))


class SileroVAD:
    """
    Silero VAD when torch + silero model are importable.

    Model weights load lazily on first use via torch.hub (may download). Prefer
    EnergyVAD when ``voice_prefer_energy_vad`` is set so startup never triggers
    a silent hub download.
    """

    name = "silero"

    def __init__(self, *, threshold: float = 0.5) -> None:
        self.threshold = threshold
        self._model: Any | None = None
        self._fallback = EnergyVAD()

    def available(self) -> bool:
        try:
            import torch  # noqa: F401

            return True
        except Exception:
            return False

    def load(self) -> None:
        if self._model is not None:
            return
        if not self.available():
            return
        import torch

        # Explicit first-use load only — never call from import/start paths.
        model, _utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=True,
        )
        self._model = model

    def is_speech_frame(self, audio: AudioChunk) -> bool:
        return self.is_speech(audio)

    def is_speech(self, audio: AudioChunk) -> bool:
        return self.speech_probability(audio) >= self.threshold

    def speech_probability(self, audio: AudioChunk) -> float:
        if not self.available():
            return self._fallback.speech_probability(audio)
        try:
            self.load()
        except Exception:
            return self._fallback.speech_probability(audio)
        if self._model is None:
            return self._fallback.speech_probability(audio)
        import torch

        samples = ensure_float32_mono(audio.samples, channels=audio.channels)
        if audio.sample_rate != 16000:
            from emily.voice.audio.processing import resample

            samples = resample(samples, audio.sample_rate, 16000)
        if samples.size < 512:
            return self._fallback.speech_probability(audio)
        tensor = torch.from_numpy(samples).float()
        try:
            prob = self._model(tensor, 16000).item()
            return float(prob)
        except Exception:
            return self._fallback.speech_probability(audio)


def create_vad(*, prefer_silero: bool = True, settings: Any | None = None) -> SileroVAD | EnergyVAD:
    """
    Build a VAD instance.

    If ``settings.voice_prefer_energy_vad`` is True, always return EnergyVAD
    (avoids torch.hub Silero download until explicitly desired).
    """
    if settings is not None and bool(getattr(settings, "voice_prefer_energy_vad", False)):
        return EnergyVAD()
    silero = SileroVAD()
    if prefer_silero and silero.available():
        return silero
    return EnergyVAD()
