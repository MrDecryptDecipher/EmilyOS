"""Extra unit tests for coverage without heavy TTS deps."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from emily.voice.audio.processing import (
    ensure_float32_mono,
    normalize,
    resample,
    silence,
    silence_for_pause,
    to_pcm_bytes,
    trim_silence,
)
from emily.voice.errors import ModelUnavailableError
from emily.voice.hardware import classify_profile, clear_hardware_cache, detect_hardware
from emily.voice.metrics import VoiceMetrics, redact_transcript
from emily.voice.models import AudioChunk, HardwareProfile, PauseProfile
from emily.voice.models_mgr.manager import ModelManager
from emily.voice.personality import DEFAULT_PERSONALITY, load_personality, save_personality
from emily.voice.speech.pauses import pause_after_text, pause_duration_ms
from emily.voice.speech.segmentation import split_sentences
from emily.voice.speech.styles import infer_emotion_from_text, style_from_personality
from emily.voice.tts.base import backends_available
from emily.voice.tts.kokoro import KokoroTTS
from emily.voice.tts.registry import capability_for
from emily.voice.vad.silero import EnergyVAD, create_vad


def test_audio_processing_pipeline() -> None:
    samples = np.array([0.0] * 20 + [0.5, -0.5] + [0.0] * 20, dtype=np.float32)
    mono = ensure_float32_mono(samples.tolist())
    trimmed = trim_silence(mono, sample_rate=16000, threshold=0.1, pad_ms=0.0)
    assert trimmed.size < mono.size
    norm = normalize(trimmed)
    assert float(np.max(np.abs(norm))) <= 0.95 + 1e-5
    up = resample(norm, 16000, 24000)
    assert up.size > norm.size
    assert silence(100, sample_rate=16000).shape[0] == 1600
    assert silence_for_pause(PauseProfile.SHORT, sample_rate=16000).size > 0
    assert isinstance(to_pcm_bytes(norm), bytes)


def test_energy_vad_and_create() -> None:
    vad = EnergyVAD(threshold=0.01, min_speech_ms=50.0)
    quiet = AudioChunk(samples=[0.0] * 3200, sample_rate=16000, channels=1)
    loud = AudioChunk(samples=[0.2] * 3200, sample_rate=16000, channels=1)
    assert vad.is_speech(quiet) is False
    assert vad.is_speech(loud) is True
    assert create_vad(prefer_silero=False).name == "energy"


def test_personality_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "personality.json"
    saved = save_personality(DEFAULT_PERSONALITY, path)
    loaded = load_personality(saved)
    assert loaded.warmth == pytest.approx(0.96)
    assert loaded.default_language == "en-IN"


def test_metrics_redaction() -> None:
    assert "redacted" in redact_transcript("hello world secret stuff")
    assert redact_transcript("hello", debug=True) == "hello"
    m = VoiceMetrics(debug=False)
    m.begin_turn()
    m.record_vad(1.0)
    m.record_asr(2.0)
    m.record_llm(3.0)
    m.mark_first_audio()
    m.record_tts(4.0, backend="kokoro")
    m.record_asr_rtf(0.5, 1.0)
    m.record_tts_rtf(0.2, 1.0)
    m.record_memory(12.5)
    m.record_e2e(99.0)
    m.record_turn()
    snap = m.snapshot()
    assert snap.turns == 1
    assert snap.last_backend == "kokoro"
    assert snap.asr_rtf == 0.5
    assert snap.tts_rtf == 0.2
    assert snap.memory_mb == 12.5
    assert snap.end_to_end_ms == 99.0


def test_model_manager_refuses_silent_download(tmp_path: Path) -> None:
    mgr = ModelManager(root=tmp_path)
    text = mgr.download_instructions("indicf5")
    assert "IndicF5" in text or "allow-download" in text.lower()
    with pytest.raises(ModelUnavailableError):
        mgr.download("indicf5", allow_download=False)
    status = mgr.check("kokoro")
    assert status.name == "kokoro"


def test_pauses_and_segmentation() -> None:
    assert pause_after_text("Really?") == PauseProfile.MEDIUM
    assert pause_after_text("Wait...") == PauseProfile.LONG
    assert pause_duration_ms(PauseProfile.MICRO) > 0
    parts = split_sentences("One. Two! Three?")
    assert len(parts) == 3


def test_styles_and_hardware() -> None:
    assert infer_emotion_from_text("This is amazing!") == "excited"
    style = style_from_personality(DEFAULT_PERSONALITY)
    assert style.value
    clear_hardware_cache()
    info = detect_hardware()
    assert info.cpu_count >= 1
    assert isinstance(info.mps_available, bool)
    assert info.onnx_hint is False
    from emily.voice.hardware import resolve_torch_device

    assert resolve_torch_device("cpu") == "cpu"
    assert classify_profile(cpu_count=2, ram_gb=4, cuda=False) == HardwareProfile.LOW


def test_kokoro_unavailable_without_package() -> None:
    eng = KokoroTTS()
    assert isinstance(eng.available(), bool)
    assert capability_for("kokoro") is not None
    assert backends_available([eng]) == (["kokoro"] if eng.available() else [])


@pytest.mark.asyncio
async def test_subsystem_disabled(tmp_path: Path) -> None:
    from pydantic import SecretStr

    from emily.config.settings import EmilySettings
    from emily.events.bus import InProcessEventBus
    from emily.kernel.context import DefaultKernelContext
    from emily.observability.logging import StructuredLogger
    from emily.observability.metrics import InMemoryMetrics
    from emily.observability.tracing import FileJSONLTracer
    from emily.voice.subsystem import VoiceSubsystem

    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        nvidia_api_key=SecretStr(""),
        routesme_api_key=SecretStr(""),
        voice_enabled=False,
        _env_file=None,
    )
    ctx = DefaultKernelContext(
        settings=settings,
        bus=InProcessEventBus(),
        logger=StructuredLogger(name="test"),
        metrics=InMemoryMetrics(export_path=tmp_path / "m.jsonl"),
        tracer=FileJSONLTracer(tmp_path / "t.jsonl"),
    )
    sub = VoiceSubsystem()
    await sub.on_start(ctx)
    assert sub._disabled is True
    health = await sub.health()
    assert health.message == "disabled"
    await sub.on_stop(ctx)


@pytest.mark.asyncio
async def test_register_voice_tools() -> None:
    from emily.tools.registry import ToolRegistry
    from emily.voice.runtime import VoiceRuntime
    from emily.voice.tools import register_voice_tools

    runtime = VoiceRuntime(settings=SimpleNamespace(voice_enabled=True, debug=False))
    registry = ToolRegistry()
    names = register_voice_tools(registry, runtime)
    assert "voice.speak" in names
    assert "voice.models" in names
