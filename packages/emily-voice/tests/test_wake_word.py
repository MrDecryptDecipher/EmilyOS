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
    assert any("Say 'Hey Emily'" in s or "Hey Emily" in s for s in statuses)


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
    assert not _should_prefer_multilingual_followup(
        "i'm charles",
        "kya haal chaal",
        detected_language="hi",
    )


def test_english_followup_is_trusted_for_clear_questions() -> None:
    from emily.voice.session.wake_word import (
        _english_followup_is_trusted,
        _english_followup_needs_retranscribe,
    )

    # Greeting-style English is often Hindi→English Whisper translation — re-check.
    assert not _english_followup_is_trusted("how are you?")
    assert _english_followup_needs_retranscribe("how are you?")
    assert _english_followup_needs_retranscribe("what's up? what are you doing")
    # Specific factual English questions stay trusted.
    assert _english_followup_is_trusted("what time is it")
    assert not _english_followup_needs_retranscribe("what time is it")
    assert _english_followup_needs_retranscribe("what's up")
    # Strong roman Hinglish must be trusted (avoid Tamil re-transcription swaps).
    assert _english_followup_is_trusted("kya hal chal kya kar rahe hai")
    assert not _english_followup_needs_retranscribe("kya hal chal kya kar rahe hai")


@pytest.mark.asyncio
async def test_resolve_wake_question_keeps_roman_hinglish() -> None:
    from emily.voice.models import AudioChunk
    from emily.voice.session.wake_word import WakeWordBackend, WakeWordHit, resolve_wake_question

    class _Asr:
        async def transcribe_wake_followup(self, audio, *, language_hint=None, on_status=None):
            raise AssertionError("should not re-transcribe clear roman Hinglish")

    hit = WakeWordHit(
        phrase="Hey Emily",
        backend=WakeWordBackend.ASR_PHRASE,
        transcript="Hey Emily, kya hal chal kya kar rahe hai?",
        audio=AudioChunk(samples=[0.0] * 160, sample_rate=16000, channels=1),
    )
    question = await resolve_wake_question(_Asr(), hit)  # type: ignore[arg-type]
    assert "kya" in question and "hai" in question


def test_should_not_prefer_tamil_over_hinglish() -> None:
    from emily.voice.session.wake_word import _should_prefer_multilingual_followup

    assert not _should_prefer_multilingual_followup(
        "kya hal chal kya kar rahe hai",
        "ஹெய்ய மிலி ஏன் கால் சால் என்ன செய்கிறீர்கள்",
        detected_language="ta",
    )


@pytest.mark.asyncio
async def test_resolve_wake_question_prefers_hinglish_over_english_greeting() -> None:
    from emily.voice.models import AudioChunk
    from emily.voice.session.wake_word import WakeWordBackend, WakeWordHit, resolve_wake_question

    class _Asr:
        last_detected_language = "hi"

        async def transcribe_wake_followup(self, audio, *, language_hint=None, on_status=None):
            assert language_hint == "hi"
            return "Hey Emily, kya kar rahe ho?"

    hit = WakeWordHit(
        phrase="Hey Emily",
        backend=WakeWordBackend.ASR_PHRASE,
        transcript="Hey Emily! What's up? What are you doing?",
        audio=AudioChunk(samples=[0.0] * 160, sample_rate=16000, channels=1),
    )
    question = await resolve_wake_question(_Asr(), hit)  # type: ignore[arg-type]
    assert "kya" in question and "ho" in question


@pytest.mark.asyncio
async def test_resolve_wake_question_keeps_english_when_hindi_asr_agrees() -> None:
    from emily.voice.models import AudioChunk
    from emily.voice.session.wake_word import WakeWordBackend, WakeWordHit, resolve_wake_question

    class _Asr:
        last_detected_language = "en"

        async def transcribe_wake_followup(self, audio, *, language_hint=None, on_status=None):
            return "Hey Emily, how are you?"

    hit = WakeWordHit(
        phrase="Hey Emily",
        backend=WakeWordBackend.ASR_PHRASE,
        transcript="Hey Emily, how are you?",
        audio=AudioChunk(samples=[0.0] * 160, sample_rate=16000, channels=1),
    )
    question = await resolve_wake_question(_Asr(), hit)  # type: ignore[arg-type]
    assert question == "how are you"


@pytest.mark.asyncio
async def test_resolve_wake_question_keeps_trusted_english() -> None:
    from emily.voice.models import AudioChunk
    from emily.voice.session.wake_word import WakeWordBackend, WakeWordHit, resolve_wake_question

    class _Asr:
        async def transcribe_wake_followup(self, audio, *, language_hint=None, on_status=None):
            raise AssertionError("should not re-transcribe trusted English follow-up")

    hit = WakeWordHit(
        phrase="Hey Emily",
        backend=WakeWordBackend.ASR_PHRASE,
        transcript="Hey Emily, I'm Charles",
        audio=AudioChunk(samples=[0.0] * 160, sample_rate=16000, channels=1),
    )
    question = await resolve_wake_question(_Asr(), hit)  # type: ignore[arg-type]
    assert question == "i'm charles"


@pytest.mark.asyncio
async def test_resolve_wake_question_retranscribes_hinglish() -> None:
    from emily.voice.models import AudioChunk
    from emily.voice.session.wake_word import WakeWordBackend, WakeWordHit, resolve_wake_question

    calls: list[str | None] = []

    class _Asr:
        last_detected_language = "hi"

        async def transcribe_wake_followup(self, audio, *, language_hint=None, on_status=None):
            return "Hey Emily, kya haal chaal?"

    hit = WakeWordHit(
        phrase="Hey Emily",
        backend=WakeWordBackend.ASR_PHRASE,
        transcript="Hey Emily, what's up?",
        audio=AudioChunk(samples=[0.0] * 160, sample_rate=16000, channels=1),
    )
    question = await resolve_wake_question(_Asr(), hit)  # type: ignore[arg-type]
    assert question == "kya haal chaal"


def test_wake_listener_disabled_without_flag() -> None:
    listener = WakeWordListener(settings=SimpleNamespace(voice_wake_word_enabled=False))
    assert not listener.enabled()
