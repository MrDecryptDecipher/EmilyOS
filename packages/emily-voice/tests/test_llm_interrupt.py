"""LLM stream cancellation via barge-in / interruption controller."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from emily.voice.errors import VoiceInterruptedError
from emily.voice.models import AudioChunk, SpeechPlan, TTSCapability
from emily.voice.session.conversation import VoiceConversationEngine


class TokenRouter:
    async def stream(self, messages):
        for piece in ("One ", "two ", "three ", "four."):
            await asyncio.sleep(0.05)
            yield piece


class SentenceRouter:
    """Yields full sentences slowly so TTS can interrupt before the next."""

    async def stream(self, messages):
        for piece in ("First sentence here. ", "Second sentence follows."):
            await asyncio.sleep(0.15)
            yield piece


@pytest.mark.asyncio
async def test_llm_stream_cancels_when_interrupted() -> None:
    engine = VoiceConversationEngine(
        settings=SimpleNamespace(
            voice_streaming=True,
            voice_barge_in=True,
            voice_adaptive_pacing=False,
            voice_emotion=False,
            voice_prefer_energy_vad=True,
        ),
        provider_router=TokenRouter(),
    )
    collected: list[str] = []

    async def consume() -> None:
        async for sentence in engine._llm_sentence_stream("hello"):
            collected.append(sentence)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.08)
    await engine.interruption.interrupt()
    with pytest.raises(VoiceInterruptedError):
        await task
    assert len(collected) <= 2


@pytest.mark.asyncio
async def test_converse_streaming_stops_after_barge_in() -> None:
    engine = VoiceConversationEngine(
        settings=SimpleNamespace(
            voice_streaming=True,
            voice_barge_in=True,
            voice_adaptive_pacing=False,
            voice_emotion=False,
            voice_prefer_energy_vad=True,
            tts_default="stub",
        ),
        provider_router=SentenceRouter(),
    )

    class InterruptTTS:
        name = "stub"

        @property
        def capabilities(self) -> TTSCapability:
            return TTSCapability(name="stub", languages=["en"], lightweight=True, priority=1)

        def available(self) -> bool:
            return True

        async def synthesize(self, plan: SpeechPlan) -> AudioChunk:
            await engine.interruption.interrupt()
            raise VoiceInterruptedError()

    engine.engines = {"stub": InterruptTTS()}

    async def fake_listen(**kwargs: object) -> str:
        return "test question"

    engine.listen_for_question = fake_listen  # type: ignore[method-assign]

    result = await engine.converse_streaming(play=True)
    assert result["state"] in {"interrupted", "idle"}
    assert "Second" not in result.get("reply", "")
