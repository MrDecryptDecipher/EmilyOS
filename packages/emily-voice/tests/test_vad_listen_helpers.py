"""VAD utterance segmentation helpers (no sounddevice required)."""

from __future__ import annotations

import numpy as np

from emily.voice.audio.capture import segment_pcm_utterance
from emily.voice.models import AudioChunk
from emily.voice.vad.silero import EnergyVAD


def _tone(n: int, amp: float = 0.2) -> np.ndarray:
    return np.full(n, amp, dtype=np.float32)


def _silence(n: int) -> np.ndarray:
    return np.zeros(n, dtype=np.float32)


def test_energy_vad_frame_speech() -> None:
    vad = EnergyVAD(threshold=0.05, min_speech_ms=120.0)
    quiet = AudioChunk(samples=[0.0] * 480, sample_rate=16000, channels=1)
    loud = AudioChunk(samples=[0.2] * 480, sample_rate=16000, channels=1)
    assert vad.is_speech_frame(quiet) is False
    assert vad.is_speech_frame(loud) is True
    assert vad.is_speech(loud) is True


def test_segment_pcm_speech_then_silence() -> None:
    sr = 16000
    frame = int(sr * 0.03)
    # 200ms silence, 300ms speech, 600ms silence
    pcm = np.concatenate(
        [
            _silence(frame * 7),
            _tone(frame * 10, 0.25),
            _silence(frame * 20),
        ]
    )
    vad = EnergyVAD(threshold=0.05, min_speech_ms=30.0)
    utterance, vad_ms = segment_pcm_utterance(
        pcm,
        sample_rate=sr,
        vad=vad,
        frame_ms=30,
        silence_ms=150,
        max_duration_s=5.0,
    )
    assert utterance.size > 0
    assert utterance.size < pcm.size
    assert float(np.max(np.abs(utterance))) >= 0.05
    assert vad_ms >= 0.0
