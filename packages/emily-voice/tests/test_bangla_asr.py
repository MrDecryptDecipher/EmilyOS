"""BanglaASR routing tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from emily.voice.asr.whisper import FasterWhisperASR
from emily.voice.models import AudioChunk


@pytest.mark.asyncio
async def test_whisper_routes_bn_to_bangla_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    bangla = MagicMock()
    bangla.available.return_value = True
    bangla.transcribe_pcm.return_value = ("আপনি কেমন আছেন", "bn", 0.92)
    bangla._model = object()

    whisper = FasterWhisperASR(
        settings=SimpleNamespace(voice_asr_model="base"),
        device="cpu",
        bangla=bangla,  # type: ignore[arg-type]
    )
    whisper._model = MagicMock()

    pcm = np.zeros(16000, dtype=np.float32)
    text, det, prob = whisper._transcribe_pcm(pcm, language="bn")
    assert text == "আপনি কেমন আছেন"
    assert det == "bn"
    assert prob == pytest.approx(0.92)
    bangla.transcribe_pcm.assert_called_once()


def test_score_prefers_bengali_transcript_for_bn_hint() -> None:
    from emily.voice.asr.language_pick import score_transcription

    bn_score = score_transcription(
        "আপনি কেমন আছেন?",
        "bn",
        0.85,
        language_hint="bn",
    )
    hi_score = score_transcription(
        "kya haal hai",
        "hi",
        0.85,
        language_hint="bn",
    )
    assert bn_score > hi_score
