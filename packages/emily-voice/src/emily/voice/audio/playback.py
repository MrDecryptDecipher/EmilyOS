"""Speaker playback with cancel/stop for barge-in."""

from __future__ import annotations

import threading
from typing import Any

import numpy as np

from emily.voice.audio.processing import ensure_float32_mono
from emily.voice.errors import BackendUnavailableError
from emily.voice.models import AudioChunk


class AudioPlayback:
    """OutputStream wrapper supporting interruptible playback."""

    def __init__(self, *, sample_rate: int = 24000, channels: int = 1, device: int | None = None) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self._cancel = threading.Event()
        self._playing = False
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

    def cancel(self) -> None:
        self._cancel.set()
        if self._stream is not None:
            try:
                self._stream.abort()
            except Exception:
                pass

    def stop(self) -> None:
        self.cancel()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._playing = False

    @property
    def is_playing(self) -> bool:
        return self._playing

    async def play(self, chunk: AudioChunk, *, allow_cancel: bool = True) -> bool:
        """Play audio. Returns False if cancelled mid-playback."""
        sd = self._require_sd()
        self._cancel.clear()
        samples = ensure_float32_mono(chunk.samples, channels=chunk.channels)
        rate = chunk.sample_rate or self.sample_rate
        self._playing = True
        try:
            if allow_cancel and self._cancel.is_set():
                return False
            sd.play(samples, rate, device=self.device)
            # Poll for cancel while blocking wait would ignore barge-in
            while sd.get_stream().active:  # type: ignore[union-attr]
                if allow_cancel and self._cancel.is_set():
                    sd.stop()
                    return False
                sd.sleep(50)
            return not self._cancel.is_set()
        except Exception:
            # Fallback: blocking play for environments without get_stream
            try:
                if allow_cancel and self._cancel.is_set():
                    return False
                sd.play(samples, rate, device=self.device)
                sd.wait()
                return not self._cancel.is_set()
            except Exception as exc:
                raise BackendUnavailableError(
                    f"audio playback failed: {exc}",
                    backend="sounddevice",
                    cause=exc,
                ) from exc
        finally:
            self._playing = False

    async def play_silence(self, duration_ms: float, *, sample_rate: int | None = None) -> bool:
        rate = sample_rate or self.sample_rate
        n = max(0, int(rate * duration_ms / 1000.0))
        return await self.play(
            AudioChunk(samples=np.zeros(n, dtype=np.float32).tolist(), sample_rate=rate, channels=1)
        )
