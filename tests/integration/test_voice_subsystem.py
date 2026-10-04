"""Integration: voice subsystem + tools via kernel (real Kokoro TTS)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from emily.config.settings import EmilySettings
from emily.core.types.tool import ToolPermissionLevel
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.tools.models import CapabilityToken
from emily.tools.subsystem import ToolsSubsystem
from emily.voice.subsystem import VoiceSubsystem
from emily.voice.tts.kokoro import KokoroTTS

pytestmark = pytest.mark.asyncio


async def test_voice_subsystem_speak_tool(tmp_path: Path) -> None:
    if not KokoroTTS().available():
        pytest.skip("kokoro is not installed; pip install 'emily-voice[kokoro]'")

    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        nvidia_api_key=SecretStr(""),
        routesme_api_key=SecretStr(""),
        tools_enabled=True,
        mcp_catalog_path=tmp_path / "catalog.json",
        voice_enabled=True,
        voice_directory=tmp_path / "voice",
        voice_models_directory=tmp_path / "models",
        tts_enable_kokoro=True,
        tts_enable_indicf5=False,
        tts_enable_chatterbox=False,
        voice_prefer_energy_vad=True,
        tool_timeout_seconds=45.0,
        _env_file=None,
    )
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ToolsSubsystem(mcp_catalog_path=tmp_path / "catalog.json"))
    kernel.register(VoiceSubsystem())
    ctx = await kernel.start()
    try:
        assert ctx.voice_runtime is not None
        result = await ctx.tool_runtime.invoke(  # type: ignore[union-attr]
            "voice.speak",
            {"text": "Yeah, that's interesting.", "play": False},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.VOICE]),
        )
        assert result.success is True
        assert "Yeah" in str(result.output.get("text", ""))
        assert result.output.get("tts_backend") == "kokoro"
    finally:
        await kernel.stop()
        assert ctx.voice_runtime is None
