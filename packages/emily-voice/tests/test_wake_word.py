"""Wake-word phrase matching tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from emily.voice.session.wake_word import WakeWordListener, _phrase_in_transcript


def test_phrase_in_transcript_emily() -> None:
    assert _phrase_in_transcript("Emily", "Hey Emily, what's up?")
    assert _phrase_in_transcript("emily", "EMILY check this")
    assert not _phrase_in_transcript("Emily", "Hello world")


def test_phrase_in_transcript_hey_emily_variants() -> None:
    assert _phrase_in_transcript("Hey Emily", "Hey Emily, what's up?")
    assert _phrase_in_transcript("Hey Emily", "Hry Emily can you hear me?")
    assert _phrase_in_transcript("Hey Emily", "Hey Emilica, how's it going?")
    assert _phrase_in_transcript("Hey Emily", "hi emily")
    assert _phrase_in_transcript("Hey Emily", "hai emily, kya haal hai")
    assert not _phrase_in_transcript("Hey Emily", "Hello world")


def test_wake_listener_asr_mode_available_flags() -> None:
    class _Cap:
        def available(self) -> bool:
            return True

    class _Asr:
        def available(self) -> bool:
            return True

    listener = WakeWordListener(
        settings=SimpleNamespace(
            voice_enabled=True,
            voice_wake_word_enabled=True,
            wake_word="Hey Emily",
            voice_wake_word_model=None,
            voice_prefer_energy_vad=True,
        ),
        capture=_Cap(),  # type: ignore[arg-type]
        asr=_Asr(),  # type: ignore[arg-type]
    )
    assert listener.backend().value == "asr_phrase"
    assert listener.enabled()


@pytest.mark.asyncio
async def test_wait_asr_phrase_uses_fixed_chunks() -> None:
    heard: list[str] = []
    statuses: list[str] = []

    class _Cap:
        def available(self) -> bool:
            return True

        async def record(self, duration_s: float = 3.0):
            from emily.voice.models import AudioChunk
            import numpy as np

            speech = (np.sin(np.linspace(0, 6, 1600)) * 0.15).astype(np.float32)
            return AudioChunk(samples=speech.tolist(), sample_rate=16000, channels=1)

    class _Asr:
        def available(self) -> bool:
            return True

        async def load(self) -> None:
            return None

        async def transcribe_wake(self, audio, *, wake_phrase=None, on_status=None):
            heard.append(wake_phrase)
            return "hey emily what is up"

    listener = WakeWordListener(
        settings=SimpleNamespace(
            voice_enabled=True,
            voice_wake_word_enabled=True,
            wake_word="Hey Emily",
            voice_wake_word_listen_chunk_s=3.0,
            voice_prefer_energy_vad=True,
        ),
        capture=_Cap(),  # type: ignore[arg-type]
        asr=_Asr(),  # type: ignore[arg-type]
        on_status=statuses.append,
    )
    hit = await listener._wait_asr_phrase()
    assert hit.phrase == "Hey Emily"
    assert hit.backend.value == "asr_phrase"
    assert heard == ["Hey Emily"]
    assert any("any language" in s.lower() or "Hey Emily" in s for s in statuses)


def test_strip_wake_phrase_followup() -> None:
    from emily.voice.session.wake_word import _strip_wake_phrase

    assert _strip_wake_phrase("Hey Emily", "hey emily what is the weather") == "what is the weather"
    assert _strip_wake_phrase("Hey Emily", "hey emily") == ""


def test_should_prefer_multilingual_over_english_hallucination() -> None:
    from emily.voice.session.wake_word import _should_prefer_multilingual_followup

    assert _should_prefer_multilingual_followup(
        "where are you going",
        "kya haal chaal",
        detected_language="hi",
    )
    assert not _should_prefer_multilingual_followup(
        "what time is it",
        "what time is it",
        detected_language="en",
    )


@pytest.mark.asyncio
async def test_resolve_wake_question_uses_multilingual_auto_detect() -> None:
    from emily.voice.models import AudioChunk
    from emily.voice.session.wake_word import WakeWordBackend, WakeWordHit, resolve_wake_question

    class _Asr:
        last_detected_language = "bn"

        async def transcribe_wake_question(self, audio, *, on_status=None, english_wake_hint=None):
            return "Hey Emily, তুমি কেমন আছো?"

    hit = WakeWordHit(
        phrase="Hey Emily",
        backend=WakeWordBackend.ASR_PHRASE,
        transcript="Hey Emily, How are you doing?",
        audio=AudioChunk(samples=[0.0] * 160, sample_rate=16000, channels=1),
    )
    question = await resolve_wake_question(_Asr(), hit)  # type: ignore[arg-type]
    assert "তুমি" in question or "কেমন" in question


@pytest.mark.asyncio
async def test_resolve_wake_question_french() -> None:
    from emily.voice.models import AudioChunk
    from emily.voice.session.wake_word import WakeWordBackend, WakeWordHit, resolve_wake_question

    class _Asr:
        last_detected_language = "fr"

        async def transcribe_wake_question(self, audio, *, on_status=None, english_wake_hint=None):
            return "Hey Emily, quelle heure est-il?"

    hit = WakeWordHit(
        phrase="Hey Emily",
        backend=WakeWordBackend.ASR_PHRASE,
        transcript="Hey Emily, what time is it?",
        audio=AudioChunk(samples=[0.0] * 160, sample_rate=16000, channels=1),
    )
    question = await resolve_wake_question(_Asr(), hit)  # type: ignore[arg-type]
    assert "quelle heure" in question


@pytest.mark.asyncio
async def test_resolve_wake_question_rejects_amili_bengali_for_how_are_you() -> None:
    """Bengali wake echo is stripped; remaining Bengali question is kept."""
    from emily.voice.models import AudioChunk
    from emily.voice.session.wake_word import WakeWordBackend, WakeWordHit, resolve_wake_question

    class _Asr:
        last_detected_language = "bn"

        async def transcribe_wake_question(self, audio, *, on_status=None, english_wake_hint=None):
            return "Hey Emily, হে আমিলি, কেমন আছে"

    hit = WakeWordHit(
        phrase="Hey Emily",
        backend=WakeWordBackend.ASR_PHRASE,
        transcript="Hey Emily, how are you?",
        audio=AudioChunk(samples=[0.0] * 160, sample_rate=16000, channels=1),
    )
    question = await resolve_wake_question(_Asr(), hit)  # type: ignore[arg-type]
    assert "কেমন" in question
    assert "আমিলি" not in question


@pytest.mark.asyncio
async def test_resolve_wake_question_rejects_urdu_hallucination_for_whats_up() -> None:
    """Hinglish greeting mis-detected as Urdu should keep English wake followup."""
    from emily.voice.models import AudioChunk
    from emily.voice.session.wake_word import WakeWordBackend, WakeWordHit, resolve_wake_question

    class _Asr:
        last_detected_language = "ur"

        async def transcribe_wake_question(self, audio, *, on_status=None, english_wake_hint=None):
            return "Hey Emily, ہی امیلی کی حال چال کیا کر رہی ہو؟"

    hit = WakeWordHit(
        phrase="Hey Emily",
        backend=WakeWordBackend.ASR_PHRASE,
        transcript="Hey Emily, what's up?",
        audio=AudioChunk(samples=[0.0] * 160, sample_rate=16000, channels=1),
    )
    question = await resolve_wake_question(_Asr(), hit)  # type: ignore[arg-type]
    assert question in ("what's up?", "what's up")


@pytest.mark.asyncio
async def test_resolve_wake_question_rejects_bengali_hallucination_for_whats_up() -> None:
    """Hinglish greeting mistranscribed as Bengali script should keep English wake followup."""
    from emily.voice.models import AudioChunk
    from emily.voice.session.wake_word import WakeWordBackend, WakeWordHit, resolve_wake_question

    class _Asr:
        last_detected_language = "bn"

        async def transcribe_wake_question(self, audio, *, on_status=None, english_wake_hint=None):
            return "Hey Emily, এই এমিলি, কিছু হাল চাল"

    hit = WakeWordHit(
        phrase="Hey Emily",
        backend=WakeWordBackend.ASR_PHRASE,
        transcript="Hey Emily, what's up?",
        audio=AudioChunk(samples=[0.0] * 160, sample_rate=16000, channels=1),
    )
    question = await resolve_wake_question(_Asr(), hit)  # type: ignore[arg-type]
    assert question in ("what's up?", "what's up")


@pytest.mark.asyncio
async def test_resolve_wake_question_fallback_without_audio() -> None:
    from emily.voice.session.wake_word import WakeWordBackend, WakeWordHit, resolve_wake_question

    class _Asr:
        async def transcribe_wake_question(self, audio, *, on_status=None, english_wake_hint=None):
            raise AssertionError("no audio — should not call ASR")

    hit = WakeWordHit(
        phrase="Hey Emily",
        backend=WakeWordBackend.ASR_PHRASE,
        transcript="Hey Emily, what time is it?",
        audio=None,
    )
    question = await resolve_wake_question(_Asr(), hit)  # type: ignore[arg-type]
    assert question == "what time is it"


def test_wake_listener_disabled_without_flag() -> None:
    listener = WakeWordListener(settings=SimpleNamespace(voice_wake_word_enabled=False))
    assert not listener.enabled()
