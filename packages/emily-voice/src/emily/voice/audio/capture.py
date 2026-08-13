"""Microphone capture via sounddevice."""

from __future__ import annotations

import time
from typing import Any, Protocol

import numpy as np

from emily.voice.errors import BackendUnavailableError
from emily.voice.models import AudioChunk


class _VADLike(Protocol):
    def is_speech(self, audio: AudioChunk) -> bool: ...


def frame_is_speech(vad: Any, chunk: AudioChunk) -> bool:
    """Frame-level speech check (energy-only when EnergyVAD provides it)."""
    fn = getattr(vad, "is_speech_frame", None)
    if callable(fn):
        return bool(fn(chunk))
    return bool(vad.is_speech(chunk))


def segment_pcm_utterance(
    samples: np.ndarray | list[float],
    *,
    sample_rate: int,
    vad: Any,
    frame_ms: int = 30,
    silence_ms: int = 500,
    max_duration_s: float = 12.0,
    channels: int = 1,
) -> tuple[np.ndarray, float]:
    """
    Pure utterance segmentation over an in-memory PCM buffer.

    Returns (utterance_samples, vad_decision_latency_ms) where latency is the
    wall time spent in VAD decisions (not capture duration).
    """
    arr = np.asarray(samples, dtype=np.float32).reshape(-1)
    frame_n = max(1, int(sample_rate * frame_ms / 1000.0))
    silence_frames_needed = max(1, int(silence_ms / max(frame_ms, 1)))
    max_samples = int(sample_rate * max_duration_s)

    speech_started = False
    silence_run = 0
    collected: list[np.ndarray] = []
    vad_ms = 0.0
    offset = 0

    while offset < arr.size and (not speech_started or sum(x.size for x in collected) < max_samples):
        frame = arr[offset : offset + frame_n]
        offset += frame_n
        if frame.size == 0:
            break
        chunk = AudioChunk(
            samples=frame.tolist(),
            sample_rate=sample_rate,
            channels=channels,
            backend="buffer",
        )
        t0 = time.perf_counter()
        speaking = frame_is_speech(vad, chunk)
        vad_ms += (time.perf_counter() - t0) * 1000.0

        if not speech_started:
            if speaking:
                speech_started = True
                collected.append(frame.copy())
                silence_run = 0
            continue

        collected.append(frame.copy())
        if speaking:
            silence_run = 0
        else:
            silence_run += 1
            if silence_run >= silence_frames_needed:
                break

    if not collected:
        return np.zeros(0, dtype=np.float32), vad_ms
    out = np.concatenate(collected).astype(np.float32, copy=False)
    if out.size > max_samples:
        out = out[:max_samples]
    return out, vad_ms


class AudioCapture:
    """Capture PCM from the default input device."""

    def __init__(self, *, sample_rate: int = 16000, channels: int = 1, device: int | None = None) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self._stream: Any | None = None

    def available(self) -> bool:
        try:
            import sounddevice  # noqa: F401

            return True
        except Exception:
            return False

    def _require_sd(self) -> Any:
        try:
            import sounddevice as sd

            return sd
        except Exception as exc:
            raise BackendUnavailableError(
                "sounddevice is not installed; pip install 'emily-voice[audio]'",
                backend="sounddevice",
                cause=exc,
            ) from exc

    async def record(self, duration_s: float = 3.0) -> AudioChunk:
        sd = self._require_sd()
        frames = int(self.sample_rate * duration_s)
        try:
            data = sd.rec(
                frames,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                device=self.device,
            )
            sd.wait()
        except Exception as exc:
            raise BackendUnavailableError(
                f"audio capture failed: {exc}",
                backend="sounddevice",
                cause=exc,
            ) from exc
        arr = np.asarray(data, dtype=np.float32).reshape(-1)
        return AudioChunk(
            samples=arr.tolist(),
            sample_rate=self.sample_rate,
            channels=self.channels,
            backend="sounddevice",
        )

    async def record_utterance(
        self,
        vad: _VADLike,
        *,
        max_duration_s: float = 12.0,
        silence_ms: int = 500,
        frame_ms: int = 30,
    ) -> AudioChunk:
        """
        Capture until speech starts (VAD), then until post-speech silence or max duration.

        Metadata includes `vad_latency_ms` (VAD decision time only) and
        `capture_duration_ms` (wall capture duration).
        """
        sd = self._require_sd()
        frame_n = max(1, int(self.sample_rate * frame_ms / 1000.0))
        silence_frames_needed = max(1, int(silence_ms / max(frame_ms, 1)))
        max_frames = max(1, int(self.sample_rate * max_duration_s / frame_n))

        speech_started = False
        silence_run = 0
        collected: list[np.ndarray] = []
        vad_ms = 0.0
        t_capture = time.perf_counter()

        try:
            for _ in range(max_frames * 4):  # allow wait-for-speech before max utterance
                data = sd.rec(
                    frame_n,
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype="float32",
                    device=self.device,
                )
                sd.wait()
                frame = np.asarray(data, dtype=np.float32).reshape(-1)
                chunk = AudioChunk(
                    samples=frame.tolist(),
                    sample_rate=self.sample_rate,
                    channels=self.channels,
                    backend="sounddevice",
                )
                t0 = time.perf_counter()
                speaking = frame_is_speech(vad, chunk)
                vad_ms += (time.perf_counter() - t0) * 1000.0

                if not speech_started:
                    if speaking:
                        speech_started = True
                        collected.append(frame)
                        silence_run = 0
                    # keep waiting for speech (bounded by outer loop)
                    continue

                collected.append(frame)
                if speaking:
                    silence_run = 0
                else:
                    silence_run += 1
                    if silence_run >= silence_frames_needed:
                        break
                if sum(x.size for x in collected) >= int(self.sample_rate * max_duration_s):
                    break
        except BackendUnavailableError:
            raise
        except Exception as exc:
            raise BackendUnavailableError(
                f"utterance capture failed: {exc}",
                backend="sounddevice",
                cause=exc,
            ) from exc

        capture_ms = (time.perf_counter() - t_capture) * 1000.0
        if not collected:
            arr = np.zeros(0, dtype=np.float32)
        else:
            arr = np.concatenate(collected).astype(np.float32, copy=False)
        return AudioChunk(
            samples=arr.tolist(),
            sample_rate=self.sample_rate,
            channels=self.channels,
            backend="sounddevice",
            metadata={
                "vad_latency_ms": vad_ms,
                "capture_duration_ms": capture_ms,
                "speech_started": speech_started,
            },
        )

    def start_stream(self, callback: Any) -> None:
        sd = self._require_sd()
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            device=self.device,
            callback=callback,
        )
        self._stream.start()

    def stop_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
