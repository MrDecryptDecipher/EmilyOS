"""Barge-in monitor tests — real VAD + handler, patched sounddevice capture only."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest

from emily.voice.audio.interruption import InterruptionController
from emily.voice.models import VoiceTurnState
from emily.voice.session.barge_in import BargeInHandler
from emily.voice.session.barge_monitor import BargeInMonitor
from emily.voice.session.turn_taking import TurnTakingController
from emily.voice.vad.silero import EnergyVAD


class _Playback:
    def __init__(self) -> None:
        self.cancelled = False

    async def play(self, chunk, *, allow_cancel: bool = True) -> bool:
        return True

    def cancel(self) -> None:
        self.cancelled = True

    def stop(self) -> None:
        self.cancelled = True


@pytest.mark.asyncio
async def test_barge_monitor_triggers_on_speech(monkeypatch: pytest.MonkeyPatch) -> None:
    turns = TurnTakingController()
    turns.begin_speak()
    playback = _Playback()
    barge = BargeInHandler(turns, InterruptionController(playback))
    vad = EnergyVAD(threshold=0.05)
    capture = SimpleNamespace(sample_rate=16000, channels=1, device=None, available=lambda: True)

    class _SD:
        @staticmethod
        def rec(frames, samplerate=16000, channels=1, dtype="float32", device=None):
            return np.full((frames, 1), 0.3, dtype=np.float32)

        @staticmethod
        def wait() -> None:
            return None

    monkeypatch.setitem(__import__("sys").modules, "sounddevice", _SD)

    mon = BargeInMonitor(
        turns=turns,
        barge_in=barge,
        capture=capture,
        vad=vad,
        settings=SimpleNamespace(voice_barge_in=True),
        poll_ms=10,
        frame_ms=30,
    )
    task = mon.start()
    assert task is not None
    await asyncio.wait_for(task, timeout=2.0)
    assert turns.state == VoiceTurnState.INTERRUPTED
    assert playback.cancelled is True
    await mon.stop()


@pytest.mark.asyncio
async def test_barge_monitor_noop_without_audio() -> None:
    turns = TurnTakingController()
    turns.begin_speak()
    playback = _Playback()
    barge = BargeInHandler(turns, InterruptionController(playback))
    mon = BargeInMonitor(
        turns=turns,
        barge_in=barge,
        capture=SimpleNamespace(available=lambda: False),
        vad=EnergyVAD(),
        settings=SimpleNamespace(voice_barge_in=True),
    )
    assert mon.start() is None
    assert turns.state == VoiceTurnState.SPEAKING
    assert playback.cancelled is False
