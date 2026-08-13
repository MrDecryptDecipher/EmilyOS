"""Failure-path and routing matrix tests (no heavy models required)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from emily.voice.errors import BackendUnavailableError, VoicePolicyError
from emily.voice.language import LanguageDetector
from emily.voice.models import SpeechPlan, SpeechStyle, TTSCapability
from emily.voice.runtime import VoiceRuntime
from emily.voice.speech.director import SpeechDirector
from emily.voice.tts.registry import TTS_CAPABILITIES
from emily.voice.tts.router import select_tts_backend


class _Down:
    def __init__(self, name: str) -> None:
        self.name = name
        self.capabilities = TTSCapability(name=name, languages=["en", "hi", "te"], priority=1)

    def available(self) -> bool:
        return False


class _Up:
    def __init__(self, name: str) -> None:
        self.name = name
        self.capabilities = TTS_CAPABILITIES.get(
            name, TTSCapability(name=name, languages=["en", "hi"], priority=1, lightweight=True)
        )

    def available(self) -> bool:
        return True


def test_fallback_when_preferred_unavailable() -> None:
    plan = SpeechPlan(text="hi", language="hi", tts_backend="indicf5", style=SpeechStyle.CASUAL)
    engines = {"indicf5": _Down("indicf5"), "kokoro": _Up("kokoro")}
    assert select_tts_backend(plan, engines) == "kokoro"


def test_gpu_absence_does_not_crash_hardware() -> None:
    from emily.voice.hardware import detect_hardware, resolve_torch_device, resolve_whisper_compute_type

    hw = detect_hardware()
    device = resolve_torch_device("auto")
    assert device in {"cpu", "cuda", "mps"}
    assert hw.profile.value in {"low", "medium", "high"}
    assert resolve_whisper_compute_type("cpu") == "int8"


def test_resolve_whisper_compute_type_pascal(monkeypatch: pytest.MonkeyPatch) -> None:
    from emily.voice.hardware import resolve_whisper_compute_type

    class _Cuda:
        @staticmethod
        def is_available() -> bool:
            return True

        @staticmethod
        def get_device_capability(_index: int) -> tuple[int, int]:
            return (6, 1)

    fake_torch = SimpleNamespace(cuda=_Cuda)
    monkeypatch.setitem(__import__("sys").modules, "torch", fake_torch)
    assert resolve_whisper_compute_type("cuda") == "float32"


def test_empty_audio_asr_path_raises_or_empty() -> None:
    from emily.voice.asr.whisper import FasterWhisperASR
    from emily.voice.models import AudioChunk

    asr = FasterWhisperASR()
    if not asr.available():
        pytest.skip("faster-whisper not installed")
    # Empty PCM should not crash the process — may yield empty transcript
    import asyncio

    async def _run() -> str:
        return await asr.transcribe(AudioChunk(samples=[], sample_rate=16000, channels=1))

    text = asyncio.run(_run())
    assert isinstance(text, str)


def test_malformed_plan_still_speakable_via_director() -> None:
    # Director always returns a SpeechPlan from raw text — never crashes
    plan = SpeechDirector().plan("Yeah, it went through.", available_backends=["kokoro"])
    assert plan.text
    assert plan.tts_backend


def test_codeswitch_routing_examples() -> None:
    det = LanguageDetector()
    director = SpeechDirector()
    cases = [
        ("Hey Emily, what's up?", "en", "kokoro"),
        ("Emily, ye transaction ek baar check karna.", "hi", {"indicf5", "kokoro", "chatterbox"}),
        ("నమస్కారం transaction successful ayinda?", "te", {"indicf5", "kokoro", "chatterbox"}),
    ]
    for text, lang_hint, backends in cases:
        state = det.detect(text)
        plan = director.plan(
            text,
            language_state=state,
            available_backends=["kokoro", "indicf5", "chatterbox"],
        )
        assert plan.language in {lang_hint, state.dominant} or plan.code_switching
        if isinstance(backends, set):
            assert plan.tts_backend in backends
        else:
            assert plan.tts_backend == backends


@pytest.mark.asyncio
async def test_policy_and_missing_backend_fail_closed() -> None:
    runtime = VoiceRuntime(settings=SimpleNamespace(voice_enabled=False, debug=False))
    await runtime.start()
    with pytest.raises(VoicePolicyError):
        await runtime.speak("hi", play=False)

    runtime2 = VoiceRuntime(
        settings=SimpleNamespace(voice_enabled=True, debug=False, tts_enable_kokoro=True),
        engines={"kokoro": _Down("kokoro")},  # type: ignore[dict-item]
    )
    await runtime2.start()
    with pytest.raises(BackendUnavailableError):
        await runtime2.speak("hi", play=False)
