from __future__ import annotations

from types import SimpleNamespace

import pytest

from emily.voice.models import AudioChunk, SpeechPlan, TTSCapability
from emily.voice.session.conversation import VoiceConversationEngine


class StubTTS:
    name = "stub"

    @property
    def capabilities(self) -> TTSCapability:
        return TTSCapability(name="stub", languages=["en", "hi", "te"], lightweight=True, priority=1, multilingual=True)

    def available(self) -> bool:
        return True

    async def load(self) -> None:
        return None

    async def unload(self) -> None:
        return None

    async def synthesize(self, plan: SpeechPlan) -> AudioChunk:
        return AudioChunk(samples=[0.0] * 32, sample_rate=24000, channels=1, backend=self.name)


class CapturingRouter:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.messages = None

    async def stream(self, messages):
        self.messages = messages
        yield self.reply


@pytest.mark.asyncio
async def test_speak_text_prefers_asr_detected_language() -> None:
    engine = VoiceConversationEngine(
        settings=SimpleNamespace(
            voice_streaming=False,
            voice_barge_in=False,
            voice_adaptive_pacing=False,
            voice_emotion=False,
            voice_prefer_energy_vad=True,
            tts_default="stub",
        ),
        engines={"stub": StubTTS()},
        asr=SimpleNamespace(last_detected_language="hi"),
    )
    engine.language.state = engine.language.state.model_copy(update={"dominant": "en"})

    plan = await engine.speak_text("Sure, I can help with that.", play=False)

    assert plan.language == "hi"
    assert plan.tts_backend == "stub"


@pytest.mark.asyncio
async def test_speak_text_hindi_reply_uses_hi_even_when_asr_says_en() -> None:
    engine = VoiceConversationEngine(
        settings=SimpleNamespace(
            voice_streaming=False,
            voice_barge_in=False,
            voice_adaptive_pacing=False,
            voice_emotion=False,
            voice_prefer_energy_vad=True,
            tts_default="stub",
        ),
        engines={"stub": StubTTS()},
        asr=SimpleNamespace(last_detected_language="en"),
    )
    plan = await engine.speak_text("Main aapke saath chat kar rahi hoon.", play=False)
    assert plan.language == "hi"
    assert plan.tts_backend == "stub"
    assert plan.segments[0].language == "hi"


@pytest.mark.asyncio
async def test_llm_prompt_includes_detected_language() -> None:
    router = CapturingRouter("नमस्ते, मैं मदद कर सकती हूं।")
    engine = VoiceConversationEngine(
        settings=SimpleNamespace(
            voice_streaming=False,
            voice_barge_in=False,
            voice_adaptive_pacing=False,
            voice_emotion=False,
            voice_prefer_energy_vad=True,
        ),
        engines={"stub": StubTTS()},
        asr=SimpleNamespace(last_detected_language="hi"),
        provider_router=router,
    )
    engine.language.state = engine.language.state.model_copy(update={"dominant": "hi", "detected_language": "hi"})

    reply = await engine._llm_stream("Mujhe madad chahiye")

    assert "मदद" in reply
    assert router.messages is not None
    assert "hi" in router.messages[1]["content"]
