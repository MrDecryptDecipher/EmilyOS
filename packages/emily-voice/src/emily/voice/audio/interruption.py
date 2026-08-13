"""Barge-in / interruption coordination."""

from __future__ import annotations

import asyncio
from typing import Any

from emily.voice.audio.playback import AudioPlayback
from emily.voice.errors import VoiceInterruptedError


class InterruptionController:
    """Coordinates stop playback + cancel generation for barge-in."""

    def __init__(self, playback: AudioPlayback | None = None) -> None:
        self.playback = playback
        self._event = asyncio.Event()
        self._generation_task: asyncio.Task[Any] | None = None

    def reset(self) -> None:
        self._event.clear()

    @property
    def interrupted(self) -> bool:
        return self._event.is_set()

    def arm_generation(self, task: asyncio.Task[Any] | None) -> None:
        self._generation_task = task

    async def interrupt(self) -> None:
        self._event.set()
        if self.playback is not None:
            self.playback.cancel()
        task = self._generation_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._generation_task = None

    def raise_if_interrupted(self) -> None:
        if self._event.is_set():
            raise VoiceInterruptedError()
