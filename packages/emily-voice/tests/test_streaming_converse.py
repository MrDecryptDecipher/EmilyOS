"""Streaming speak path with real Kokoro synthesis."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from emily.voice.models import VoiceTurnState
from emily.voice.session.conversation import VoiceConversationEngine
from emily.voice.tts.kokoro import KokoroTTS


@pytest.mark.asyncio
async def test_speak_text_with_kokoro(require_kokoro: None, tmp_path) -> None:
    engine = VoiceConversationEngine(
        settings=SimpleNamespace(
            voice_streaming=True,
            voice_barge_in=False,
            voice_adaptive_pacing=True,
            voice_emotion=True,
            voice_prefer_energy_vad=True,
            voice_directory=tmp_path,
            tts_enable_kokoro=True,
            tts_enable_indicf5=False,
            tts_enable_chatterbox=False,
            tts_device="cpu",
        ),
        engines={"kokoro": KokoroTTS()},
    )
    plan = await engine.speak_text("Yeah, I checked that. The transaction went through.", play=False)
    assert plan.tts_backend == "kokoro"
    assert "checked" in plan.text.lower() or "transaction" in plan.text.lower()
    assert engine.state in {VoiceTurnState.IDLE, VoiceTurnState.SPEAKING, VoiceTurnState.THINKING}
