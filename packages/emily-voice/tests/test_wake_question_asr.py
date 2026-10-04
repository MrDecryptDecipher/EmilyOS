"""Language-agnostic wake question ASR tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from emily.voice.asr.whisper import FasterWhisperASR
from emily.voice.models import AudioChunk


@pytest.mark.asyncio
async def test_transcribe_wake_question_auto_detect_french() -> None:
    asr = FasterWhisperASR(settings=SimpleNamespace(voice_asr_model="base"), device="cpu")
    asr._model = MagicMock()

    with patch.object(
        asr,
        "_transcribe_universal",
        return_value=("bonjour", "fr", 0.88, False),
    ):
        text = await asr.transcribe_wake_question(
            AudioChunk(samples=[0.0] * 160, sample_rate=16000, channels=1),
        )

    assert text == "bonjour"
    assert asr.last_detected_language == "fr"


@pytest.mark.asyncio
async def test_transcribe_wake_question_bangla_only_when_detected_bn() -> None:
    bangla = MagicMock()
    bangla.available.return_value = True
    bangla._model = object()
    bangla.transcribe_pcm.return_value = ("তুমি কেমন আছো", "bn", 0.92)

    asr = FasterWhisperASR(
        settings=SimpleNamespace(voice_asr_model="base"),
        device="cpu",
        bangla=bangla,  # type: ignore[arg-type]
    )
    asr._model = MagicMock()
    pcm = np.zeros(16000, dtype=np.float32)

    with patch.object(
        asr,
        "_transcribe_pcm",
        return_value=("", "bn", 0.75),
    ):
        text, det, prob, retried = asr._transcribe_universal(pcm, vad_filter=False)

    assert det == "bn"
    assert "তুমি" in text
    bangla.transcribe_pcm.assert_called_once()


@pytest.mark.asyncio
async def test_transcribe_wake_question_hindi_uses_whisper_not_bangla() -> None:
    bangla = MagicMock()
    bangla.available.return_value = True
    bangla._model = object()

    asr = FasterWhisperASR(
        settings=SimpleNamespace(voice_asr_model="base"),
        device="cpu",
        bangla=bangla,  # type: ignore[arg-type]
    )
    asr._model = MagicMock()

    with patch.object(
        asr,
        "_transcribe_pcm",
        side_effect=[
            ("kya haal", "hi", 0.69),
            ("क्या हाल", "hi", 0.85),
        ],
    ) as mock_pcm:
        text, det, _, _ = asr._transcribe_universal(np.zeros(16000, dtype=np.float32))

    assert det == "hi"
    bangla.transcribe_pcm.assert_not_called()
    assert mock_pcm.call_count == 2


def test_transcribe_universal_mid_confidence_bn_still_uses_bangla() -> None:
    """Real Bengali often lands ~0.55–0.70 — must still use BanglaASR, not remapped to Hindi."""
    bangla = MagicMock()
    bangla.available.return_value = True
    bangla._model = object()
    bangla.transcribe_pcm.return_value = ("তুমি কেমন আছো", "bn", 0.88)

    asr = FasterWhisperASR(
        settings=SimpleNamespace(voice_asr_model="base"),
        device="cpu",
        bangla=bangla,  # type: ignore[arg-type]
    )
    asr._model = MagicMock()

    with patch.object(
        asr,
        "_transcribe_pcm",
        return_value=("tumi kemon", "bn", 0.61),
    ):
        text, det, _, retried = asr._transcribe_universal(np.zeros(16000, dtype=np.float32))

    assert det == "bn"
    assert "তুমি" in text
    assert retried is True
    bangla.transcribe_pcm.assert_called_once()


def test_transcribe_universal_roman_bangla_cues_use_bangla() -> None:
    bangla = MagicMock()
    bangla.available.return_value = True
    bangla._model = object()
    bangla.transcribe_pcm.return_value = ("তুমি কেমন আছো", "bn", 0.90)

    asr = FasterWhisperASR(
        settings=SimpleNamespace(voice_asr_model="base"),
        device="cpu",
        bangla=bangla,  # type: ignore[arg-type]
    )
    asr._model = MagicMock()

    with patch.object(
        asr,
        "_transcribe_pcm",
        return_value=("Hey Emily tumi kemon acho", "en", 0.55),
    ):
        text, det, _, _ = asr._transcribe_universal(np.zeros(16000, dtype=np.float32))

    assert det == "bn"
    assert "তুমি" in text
    bangla.transcribe_pcm.assert_called_once()


def test_transcribe_universal_low_confidence_ur_refines_hi() -> None:
    bangla = MagicMock()
    bangla.available.return_value = True

    asr = FasterWhisperASR(
        settings=SimpleNamespace(voice_asr_model="base"),
        device="cpu",
        bangla=bangla,  # type: ignore[arg-type]
    )
    asr._model = MagicMock()

    with patch.object(
        asr,
        "_transcribe_pcm",
        side_effect=[
            ("", "ur", 0.45),
            ("kya haal", "hi", 0.82),
        ],
    ) as mock_pcm:
        text, det, _, retried = asr._transcribe_universal(np.zeros(16000, dtype=np.float32))

    assert det == "hi"
    assert text == "kya haal"
    assert retried is True
    bangla.transcribe_pcm.assert_not_called()
    assert mock_pcm.call_args_list[1].kwargs.get("language") == "hi"


def test_maybe_bangla_wake_retry_on_english_greeting_and_hindi_garbage() -> None:
    bangla = MagicMock()
    bangla.available.return_value = True
    bangla._model = object()
    bangla.transcribe_pcm.return_value = ("তুমি কেমন আছো", "bn", 0.91)

    asr = FasterWhisperASR(
        settings=SimpleNamespace(voice_asr_model="base"),
        device="cpu",
        bangla=bangla,  # type: ignore[arg-type]
    )
    garbage = (
        "आचारा आचां ख़रिँ नार लगता आचारा आचार और ख़र मिली केमाणा चोए "
        "प्दिखा अचा दिच्छा एक तैए देठे आता"
    )
    text, det, prob, retried = asr._maybe_bangla_wake_retry(
        np.zeros(16000, dtype=np.float32),
        garbage,
        "hi",
        1.0,
        True,
        "how are you?",
        None,
    )
    assert det == "bn"
    assert "তুমি" in (text or "")
    assert retried is True
    bangla.transcribe_pcm.assert_called_once()


def test_maybe_bangla_wake_retry_skips_low_confidence_french() -> None:
    """Low-confidence non-Indic detect must not auto-run BanglaASR."""
    bangla = MagicMock()
    bangla.available.return_value = True

    asr = FasterWhisperASR(
        settings=SimpleNamespace(voice_asr_model="base"),
        device="cpu",
        bangla=bangla,  # type: ignore[arg-type]
    )
    text, det, prob, retried = asr._maybe_bangla_wake_retry(
        np.zeros(16000, dtype=np.float32),
        "bonjour comment allez-vous",
        "fr",
        0.38,
        True,
        "what time is it",
        None,
    )
    assert det == "fr"
    assert text == "bonjour comment allez-vous"
    bangla.transcribe_pcm.assert_not_called()


def test_maybe_bangla_wake_retry_skips_confident_hinglish() -> None:
    bangla = MagicMock()
    bangla.available.return_value = True

    asr = FasterWhisperASR(
        settings=SimpleNamespace(voice_asr_model="base"),
        device="cpu",
        bangla=bangla,  # type: ignore[arg-type]
    )
    text, det, _, _ = asr._maybe_bangla_wake_retry(
        np.zeros(16000, dtype=np.float32),
        "kya haal hai bhai",
        "hi",
        0.82,
        True,
        "what's up",
        None,
    )
    assert det == "hi"
    assert "kya haal" in (text or "")
    bangla.transcribe_pcm.assert_not_called()


def test_maybe_bangla_wake_retry_on_english_greeting_echo() -> None:
    """Whisper repeats English wake text — still probe BanglaASR."""
    bangla = MagicMock()
    bangla.available.return_value = True
    bangla._model = object()
    bangla.transcribe_pcm.return_value = ("তুমি কেমন আছো", "bn", 0.91)

    asr = FasterWhisperASR(
        settings=SimpleNamespace(voice_asr_model="base"),
        device="cpu",
        bangla=bangla,  # type: ignore[arg-type]
    )
    text, det, _, retried = asr._maybe_bangla_wake_retry(
        np.zeros(16000, dtype=np.float32),
        "how are you",
        "en",
        0.62,
        False,
        "how are you?",
        None,
    )
    assert det == "bn"
    assert "তুমি" in (text or "")
    assert retried is True
    bangla.transcribe_pcm.assert_called_once()


def test_maybe_bangla_wake_retry_on_english_greeting_low_conf_empty() -> None:
    """Bengali after English wake greeting: low-confidence empty → try BanglaASR."""
    bangla = MagicMock()
    bangla.available.return_value = True
    bangla._model = object()
    bangla.transcribe_pcm.return_value = ("তুমি কেমন আছো", "bn", 0.88)

    asr = FasterWhisperASR(
        settings=SimpleNamespace(voice_asr_model="base"),
        device="cpu",
        bangla=bangla,  # type: ignore[arg-type]
    )
    text, det, _, retried = asr._maybe_bangla_wake_retry(
        np.zeros(16000, dtype=np.float32),
        "",
        "en",
        0.32,
        False,
        "how are you?",
        None,
    )
    assert det == "bn"
    assert "তুমি" in (text or "")
    assert retried is True
    bangla.transcribe_pcm.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_wake_question_strips_bengali_wake_keeps_question() -> None:
    from emily.voice.models import AudioChunk
    from emily.voice.session.wake_word import WakeWordBackend, WakeWordHit, resolve_wake_question

    class _Asr:
        last_detected_language = "bn"

        async def transcribe_wake_question(self, audio, *, on_status=None, english_wake_hint=None):
            return "হে অ্যামিলি কেমন আছে"

    hit = WakeWordHit(
        phrase="Hey Emily",
        backend=WakeWordBackend.ASR_PHRASE,
        transcript="Hey Emily, how are you?",
        audio=AudioChunk(samples=[0.0] * 160, sample_rate=16000, channels=1),
    )
    question = await resolve_wake_question(_Asr(), hit)  # type: ignore[arg-type]
    assert "কেমন" in question
    assert "অ্যামিলি" not in question


@pytest.mark.asyncio
async def test_resolve_wake_question_prefers_bengali_over_hindi_garbage() -> None:
    from emily.voice.models import AudioChunk
    from emily.voice.session.wake_word import WakeWordBackend, WakeWordHit, resolve_wake_question

    class _Asr:
        last_detected_language = "bn"

        async def transcribe_wake_question(self, audio, *, on_status=None, english_wake_hint=None):
            assert "how are you" in (english_wake_hint or "")
            return "Hey Emily, তুমি কেমন আছো"

    hit = WakeWordHit(
        phrase="Hey Emily",
        backend=WakeWordBackend.ASR_PHRASE,
        transcript="Hey Emily, how are you?",
        audio=AudioChunk(samples=[0.0] * 160, sample_rate=16000, channels=1),
    )
    question = await resolve_wake_question(_Asr(), hit)  # type: ignore[arg-type]
    assert "তুমি" in question or "কেমন" in question
