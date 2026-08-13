"""Runtime policy + real Kokoro integration tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from emily.voice.errors import VoicePolicyError
from emily.voice.runtime import VoiceRuntime
from emily.voice.tts.kokoro import KokoroTTS


@pytest.mark.asyncio
async def test_policy_denies_when_voice_disabled() -> None:
    runtime = VoiceRuntime(settings=SimpleNamespace(voice_enabled=False, debug=False))
    await runtime.start()
    with pytest.raises(VoicePolicyError):
        await runtime.speak("hello", play=False)


@pytest.mark.asyncio
async def test_speak_with_kokoro(require_kokoro: None) -> None:
    runtime = VoiceRuntime(
        settings=SimpleNamespace(
            voice_enabled=True,
            debug=True,
            tts_enable_kokoro=True,
            tts_enable_indicf5=False,
            tts_enable_chatterbox=False,
            tts_device="cpu",
            voice_prefer_energy_vad=True,
        ),
    )
    try:
        await runtime.start()
        plan = await runtime.speak("Hello from Emily.", play=False)
        assert plan.tts_backend == "kokoro"
        assert plan.text
        status = await runtime.status()
        assert status.enabled is True
        assert status.backends.get("kokoro") is True
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_barge_in_marks_interrupted() -> None:
    runtime = VoiceRuntime(
        settings=SimpleNamespace(
            voice_enabled=True,
            debug=False,
            tts_enable_kokoro=False,
            tts_enable_indicf5=False,
            tts_enable_chatterbox=False,
        ),
    )
    try:
        await runtime.start()
        assert runtime.engine is not None
        runtime.engine.turns.begin_speak()
        result = await runtime.barge_in()
        assert result["interrupted"] is True
        assert result["state"] == "interrupted"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_model_status_no_download() -> None:
    runtime = VoiceRuntime(settings=SimpleNamespace(voice_enabled=True))
    models = runtime.model_status()
    assert any(m["name"] == "kokoro" for m in models)
    assert all("download_instructions" in m for m in models)


def test_kokoro_adapter_reports_availability() -> None:
    engine = KokoroTTS()
    assert engine.available() == KokoroTTS().available()
