"""Audio postprocess fade / normalize tests."""

from __future__ import annotations

import numpy as np

from emily.voice.audio.processing import fade, postprocess_for_playback
from emily.voice.models import AudioChunk


def test_fade_edges() -> None:
    samples = np.ones(1600, dtype=np.float32)
    out = fade(samples, sample_rate=16000, fade_ms=10.0)
    assert float(out[0]) < float(out[len(out) // 2])
    assert float(out[-1]) < float(out[len(out) // 2])


def test_postprocess_for_playback() -> None:
    raw = [0.0] * 200 + [0.5] * 400 + [0.0] * 200
    chunk = AudioChunk(samples=raw, sample_rate=16000, channels=1, backend="test")
    out = postprocess_for_playback(chunk)
    assert out.metadata.get("postprocessed") is True
    assert len(out.samples) > 0
    assert len(out.samples) <= len(raw)
    assert max(abs(x) for x in out.samples) <= 0.95 + 1e-5
