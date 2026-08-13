"""Auto barge-in monitor while Emily is speaking."""

from __future__ import annotations

import asyncio
from typing import Any

from emily.voice.models import AudioChunk, VoiceTurnState
from emily.voice.session.barge_in import BargeInHandler
from emily.voice.settings_bridge import voice_flag


class BargeInMonitor:
    """
    Poll short mic frames with VAD while state == SPEAKING.

    No-op when sounddevice is unavailable or voice_barge_in is False.
    """

    def __init__(
        self,
        *,
        turns: Any,
        barge_in: BargeInHandler,
        capture: Any | None = None,
        vad: Any | None = None,
        settings: Any | None = None,
        poll_ms: int = 80,
        frame_ms: int = 30,
    ) -> None:
        self.turns = turns
        self.barge_in = barge_in
        self.capture = capture
        self.vad = vad
        self.settings = settings
        self.poll_ms = poll_ms
        self.frame_ms = frame_ms
        self._task: asyncio.Task[None] | None = None

    def enabled(self) -> bool:
        if not bool(voice_flag(self.settings, "voice_barge_in", True)):
            return False
        if self.capture is None or self.vad is None:
            return False
        available = getattr(self.capture, "available", None)
        if callable(available) and not available():
            return False
        return True

    def start(self) -> asyncio.Task[None] | None:
        if not self.enabled():
            return None
        if self._task is not None and not self._task.done():
            return self._task
        self._task = asyncio.create_task(self._run(), name="voice-barge-monitor")
        return self._task

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def _run(self) -> None:
        from emily.voice.audio.capture import frame_is_speech

        capture = self.capture
        vad = self.vad
        assert capture is not None and vad is not None
        sample_rate = int(getattr(capture, "sample_rate", 16000))
        channels = int(getattr(capture, "channels", 1))
        frame_n = max(1, int(sample_rate * self.frame_ms / 1000.0))

        while True:
            if getattr(self.turns, "state", None) != VoiceTurnState.SPEAKING:
                await asyncio.sleep(self.poll_ms / 1000.0)
                continue
            try:
                # Prefer a short record if sounddevice path exists
                sd = None
                try:
                    import sounddevice as sd  # type: ignore[assignment]
                except Exception:
                    return
                data = sd.rec(
                    frame_n,
                    samplerate=sample_rate,
                    channels=channels,
                    dtype="float32",
                    device=getattr(capture, "device", None),
                )
                sd.wait()
                import numpy as np

                frame = np.asarray(data, dtype=np.float32).reshape(-1)
                chunk = AudioChunk(
                    samples=frame.tolist(),
                    sample_rate=sample_rate,
                    channels=channels,
                    backend="barge_monitor",
                )
                if frame_is_speech(vad, chunk):
                    await self.barge_in.trigger()
                    return
            except asyncio.CancelledError:
                raise
            except Exception:
                # Safe no-op on capture failures
                await asyncio.sleep(self.poll_ms / 1000.0)
                continue
            await asyncio.sleep(0)
