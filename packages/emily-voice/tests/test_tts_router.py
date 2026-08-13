"""TTS router scoring and fallback tests."""

from __future__ import annotations

from emily.voice.errors import BackendUnavailableError
from emily.voice.models import SpeechPlan, SpeechStyle, TTSCapability
from emily.voice.tts.router import fallback_chain, score_backend, select_tts_backend


class _StubEngine:
    def __init__(self, name: str, available_flag: bool = True) -> None:
        self.name = name
        self._available = available_flag
        self.capabilities = TTSCapability(name=name, languages=["en", "hi"], priority=1)

    def available(self) -> bool:
        return self._available


def test_score_prefers_plan_backend_and_language() -> None:
    from emily.voice.models import HardwareProfile
    from types import SimpleNamespace

    plan = SpeechPlan(text="hi", language="hi", tts_backend="indicf5", style=SpeechStyle.WARM)
    heavy_ok = SimpleNamespace(tts_device="cpu", voice_tts_prefer_lightweight=False)
    s_indic = score_backend(
        "indicf5", plan, available=True, hardware_profile=HardwareProfile.MEDIUM, settings=heavy_ok
    )
    s_kokoro = score_backend(
        "kokoro", plan, available=True, hardware_profile=HardwareProfile.MEDIUM, settings=heavy_ok
    )
    assert s_indic > s_kokoro


def test_score_prefers_kokoro_on_cpu_for_hindi() -> None:
    from types import SimpleNamespace

    plan = SpeechPlan(text="नमस्ते", language="hi", tts_backend="indicf5")
    cpu_settings = SimpleNamespace(tts_device="cpu", voice_tts_prefer_lightweight=True)
    assert score_backend("kokoro", plan, available=True, settings=cpu_settings) > score_backend(
        "indicf5", plan, available=True, settings=cpu_settings
    )


def test_fallback_chain_pins_plan_backend() -> None:
    plan = SpeechPlan(text="x", language="en", tts_backend="kokoro")
    chain = fallback_chain(plan, available_names=["chatterbox", "kokoro", "indicf5"])
    assert chain[0] == "kokoro"


def test_select_with_pin_consistency() -> None:
    plan = SpeechPlan(text="x", language="en", tts_backend="chatterbox")
    engines = {
        "kokoro": _StubEngine("kokoro"),
        "chatterbox": _StubEngine("chatterbox"),
    }
    assert select_tts_backend(plan, engines, pinned="kokoro") == "kokoro"


def test_select_raises_when_none_available() -> None:
    plan = SpeechPlan(text="x", language="en")
    engines = {"kokoro": _StubEngine("kokoro", available_flag=False)}
    try:
        select_tts_backend(plan, engines)
        raised = False
    except BackendUnavailableError:
        raised = True
    assert raised


def test_score_prefers_kokoro_for_hindi_when_voicebox_default() -> None:
    from types import SimpleNamespace

    plan = SpeechPlan(
        text="हाँ, बस यहीं हूँ।",
        language="hi",
        tts_backend="voicebox",
    )
    settings = SimpleNamespace(
        tts_default="voicebox",
        tts_device="cuda",
        voice_tts_prefer_lightweight=False,
    )
    s_kokoro = score_backend("kokoro", plan, available=True, settings=settings)
    s_indic = score_backend("indicf5", plan, available=True, settings=settings)
    assert s_kokoro > s_indic


def test_unavailable_backend_fallback_chain() -> None:
    plan = SpeechPlan(text="x", language="hi", tts_backend="indicf5")
    engines = {
        "indicf5": _StubEngine("indicf5", available_flag=False),
        "kokoro": _StubEngine("kokoro", available_flag=True),
        "chatterbox": _StubEngine("chatterbox", available_flag=False),
    }
    assert select_tts_backend(plan, engines) == "kokoro"
    chain = fallback_chain(plan, available_names=["kokoro"])
    assert chain == ["kokoro"]
