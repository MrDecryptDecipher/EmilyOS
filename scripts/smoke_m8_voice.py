"""Milestone 8 smoke — voice director, router, policy, subsystem (real backends only)."""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from pydantic import SecretStr

from emily.config.settings import EmilySettings
from emily.core.types.tool import ToolPermissionLevel
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.tools.models import CapabilityToken
from emily.tools.subsystem import ToolsSubsystem
from emily.voice.adaptation import UserAdaptation
from emily.voice.audio.processing import fade, postprocess_for_playback
from emily.voice.language import LanguageDetector
from emily.voice.models import (
    AudioChunk,
    LanguageState,
    SpeechPlan,
    SpeechStyle,
    TTSCapability,
    VoiceTurnState,
)
from emily.voice.runtime import VoiceRuntime
from emily.voice.session.conversation import buffer_sentences
from emily.voice.session.turn_taking import TurnTakingController
from emily.voice.settings_bridge import enabled_backends, voice_flag
from emily.voice.speech.director import SpeechDirector
from emily.voice.subsystem import VoiceSubsystem
from emily.voice.tts.chatterbox import ChatterboxTTS
from emily.voice.tts.indicf5 import IndicF5TTS
from emily.voice.tts.kokoro import KokoroTTS
from emily.voice.tts.registry import TTS_CAPABILITIES
from emily.voice.tts.router import select_tts_backend


@dataclass
class ProbeResult:
    name: str
    ok: bool
    detail: str
    skipped: bool = False


def _kokoro_available() -> bool:
    return KokoroTTS().available()


async def probe_director() -> ProbeResult:
    director = SpeechDirector()
    plan = director.plan(
        "Haan bhai, ek second... check karta hoon.",
        language_state=LanguageState(dominant="hi", secondary="en", code_switching=True),
        available_backends=["kokoro", "indicf5"],
    )
    ok = plan.tts_backend in {"kokoro", "indicf5"} and "ummm" not in plan.text.lower()
    return ProbeResult("voice:director+codeswitch", ok, f"backend={plan.tts_backend} lang={plan.language}")


async def probe_router() -> ProbeResult:
    plan = SpeechPlan(text="check", language="te", style=SpeechStyle.CASUAL, tts_backend="indicf5")

    class _CapabilityProbe:
        """Router scoring probe — uses real TTS capability metadata, not synthesis."""

        def __init__(self, name: str) -> None:
            self.name = name
            self.capabilities = TTS_CAPABILITIES[name]

        def available(self) -> bool:
            return True

    engines = {n: _CapabilityProbe(n) for n in ("kokoro", "indicf5", "chatterbox")}
    choice = select_tts_backend(plan, engines)
    ok = choice in {"indicf5", "kokoro", "chatterbox"}
    return ProbeResult("voice:tts_router", ok, f"choice={choice}")


async def probe_language() -> ProbeResult:
    det = LanguageDetector()
    det.update("How are you?")
    state = det.update("Accha, ek kaam kar.")
    ok = (state.dominant.startswith("hi") or state.code_switching) and state.sticky
    return ProbeResult("voice:language_sticky", ok, f"dominant={state.dominant} cs={state.code_switching}")


async def probe_barge_in() -> ProbeResult:
    ctrl = TurnTakingController()
    ctrl.begin_speak()
    ctrl.interrupt()
    ok = ctrl.state == VoiceTurnState.INTERRUPTED
    return ProbeResult("voice:barge_in_state", ok, f"state={ctrl.state}")


async def probe_settings_bridge() -> ProbeResult:
    engines = {
        "kokoro": KokoroTTS(),
        "indicf5": IndicF5TTS(),
        "chatterbox": ChatterboxTTS(),
    }
    settings = SimpleNamespace(
        tts_enable_kokoro=True,
        tts_enable_indicf5=False,
        tts_enable_chatterbox=False,
        voice_streaming=True,
    )
    out = enabled_backends(settings, engines)
    ok = list(out.keys()) == ["kokoro"]
    ok = ok and voice_flag(settings, "voice_streaming", False) is True
    return ProbeResult("voice:settings_bridge", ok, f"backends={sorted(out)}")


async def probe_adaptation(root: Path) -> ProbeResult:
    adapt = UserAdaptation(path=root / "adaptation.json")
    adapt.observe_user_turn("hey yeah cool")
    adapt.observe_interrupt()
    ok = adapt.profile.turn_count == 1 and adapt.profile.interrupt_count == 1
    return ProbeResult("voice:adaptation", ok, f"turns={adapt.profile.turn_count}")


async def probe_postprocess() -> ProbeResult:
    chunk = AudioChunk(samples=[0.0] * 50 + [0.4] * 200 + [0.0] * 50, sample_rate=16000)
    out = postprocess_for_playback(chunk)
    faded = fade([1.0] * 800, 16000, fade_ms=5.0)
    ok = out.metadata.get("postprocessed") is True and float(faded[0]) < 1.0
    return ProbeResult("voice:postprocess", ok, f"samples={len(out.samples)}")


async def probe_sentence_buffer() -> ProbeResult:
    done, buf = buffer_sentences("Hi there. More", "")
    ok = done == ["Hi there."] and buf == "More"
    return ProbeResult("voice:sentence_buffer", ok, f"done={done!r} buf={buf!r}")


async def probe_speak_kokoro(root: Path) -> ProbeResult:
    if not _kokoro_available():
        return ProbeResult(
            "voice:speak_kokoro",
            True,
            "SKIP: kokoro not installed",
            skipped=True,
        )
    settings = SimpleNamespace(
        voice_enabled=True,
        voice_directory=root,
        voice_models_directory=root / "models",
        debug=False,
        tts_default="kokoro",
        voice_streaming=True,
        voice_barge_in=False,
        voice_adaptive_pacing=False,
        voice_emotion=False,
        voice_prefer_energy_vad=True,
        tts_enable_kokoro=True,
        tts_enable_indicf5=False,
        tts_enable_chatterbox=False,
        tts_device="cpu",
    )
    runtime = VoiceRuntime(settings=settings)
    try:
        await runtime.start()
        plan = await runtime.speak("Yeah, it went through.", play=False)
        ok = plan.tts_backend == "kokoro" and bool(plan.text)
        return ProbeResult("voice:speak_kokoro", ok, f"backend={plan.tts_backend}")
    finally:
        await runtime.stop()


async def probe_kernel(root: Path) -> ProbeResult:
    if not _kokoro_available():
        return ProbeResult(
            "voice:kernel+tools",
            True,
            "SKIP: kokoro not installed",
            skipped=True,
        )
    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        nvidia_api_key=SecretStr(""),
        routesme_api_key=SecretStr(""),
        tools_enabled=True,
        mcp_catalog_path=root / "catalog.json",
        voice_enabled=True,
        voice_directory=root / "voice",
        voice_models_directory=root / "models",
        tts_enable_kokoro=True,
        tts_enable_indicf5=False,
        tts_enable_chatterbox=False,
        _env_file=None,
    )
    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ToolsSubsystem(mcp_catalog_path=root / "catalog.json"))
    kernel.register(VoiceSubsystem())
    ctx = await kernel.start()
    try:
        assert ctx.voice_runtime is not None
        result = await ctx.tool_runtime.invoke(  # type: ignore[union-attr]
            "voice.speak",
            {"text": "Hello from Emily.", "play": False},
            capabilities=CapabilityToken(granted=[ToolPermissionLevel.VOICE]),
        )
        health = await kernel.health()
        voice = next(s for s in health["subsystems"] if s["name"] == "voice")
        ok = result.success and voice["healthy"]
        backend = ""
        if isinstance(result.output, dict):
            backend = str(result.output.get("tts_backend", ""))
        return ProbeResult(
            "voice:kernel+tools",
            ok,
            f"ok={result.success} healthy={voice['healthy']} backend={backend or 'kokoro'}",
        )
    finally:
        await kernel.stop()


async def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="emily-m8-"))
    probes = [
        await probe_director(),
        await probe_router(),
        await probe_language(),
        await probe_barge_in(),
        await probe_settings_bridge(),
        await probe_adaptation(root),
        await probe_postprocess(),
        await probe_sentence_buffer(),
        await probe_speak_kokoro(root),
        await probe_kernel(root),
    ]
    width = max(len(p.name) for p in probes)
    passed = 0
    skipped = 0
    for probe in probes:
        if probe.skipped:
            mark = "SKIP"
            skipped += 1
            passed += 1
        else:
            mark = "PASS" if probe.ok else "FAIL"
            if probe.ok:
                passed += 1
        print(f"[{mark}] {probe.name:<{width}}  {probe.detail}")
    required = [p for p in probes if not p.skipped]
    required_ok = sum(1 for p in required if p.ok)
    print(
        f"\n{passed}/{len(probes)} probes passed "
        f"({required_ok}/{len(required)} required; {skipped} skipped without kokoro)"
    )
    return 0 if passed == len(probes) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
