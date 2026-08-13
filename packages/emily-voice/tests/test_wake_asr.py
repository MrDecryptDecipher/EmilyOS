"""Wake ASR and mic level helpers."""

from __future__ import annotations

import numpy as np

from emily.voice.audio.processing import chunk_has_speech, chunk_rms
from emily.voice.models import AudioChunk


def test_chunk_rms_silence_vs_speech() -> None:
    silent = AudioChunk(samples=[0.0] * 1600, sample_rate=16000, channels=1)
    loud = AudioChunk(samples=(np.sin(np.linspace(0, 8, 1600)) * 0.2).tolist(), sample_rate=16000, channels=1)
    assert chunk_rms(silent) < 0.001
    assert chunk_rms(loud) > 0.05
    assert not chunk_has_speech(silent)
    assert chunk_has_speech(loud)
