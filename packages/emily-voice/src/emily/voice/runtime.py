"""Voice runtime facade."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from emily.voice.asr.bangla_asr import BanglaASR
from emily.voice.asr.whisper import FasterWhisperASR
from emily.voice.audio.capture import AudioCapture
from emily.voice.audio.playback import AudioPlayback
from emily.voice.errors import BackendUnavailableError
from emily.voice.hardware import detect_hardware
from emily.voice.metrics import VoiceMetrics
from emily.voice.models import SpeechPlan, VoiceStatus, VoiceTurnState
from emily.voice.models_mgr.manager import ModelManager
from emily.voice.personality import load_personality
from emily.voice.policy import VoicePolicy
from emily.voice.session.conversation import VoiceConversationEngine
from emily.voice.session.wake_word import WakeWordHit, WakeWordListener, resolve_wake_question
from emily.voice.settings_bridge import enabled_backends, resolve_device, voice_flag
from emily.voice.tts.base import TTSEngine
from emily.voice.tts.chatterbox import ChatterboxTTS
from emily.voice.tts.indicf5 import IndicF5TTS
from emily.voice.tts.kokoro import KokoroTTS
from emily.voice.tts.voicebox import VoiceboxTTS
from emily.voice.ui_server import VoiceStatusServer


class VoiceRuntime:
    """Primary API for Emily voice: speak, listen, converse, barge-in, models."""

    def __init__(
        self,
        *,
        settings: Any | None = None,
        event_bus: Any | None = None,
        logger: Any | None = None,
        provider_router: Any | None = None,
        engines: dict[str, TTSEngine] | None = None,
        asr: FasterWhisperASR | None = None,
        capture: AudioCapture | None = None,
        playback: AudioPlayback | None = None,
    ) -> None:
        self.settings = settings
        self.event_bus = event_bus
        self.logger = logger
        self.provider_router = provider_router
        self.policy = VoicePolicy(settings)
        self.metrics = VoiceMetrics(
            logger=logger,
            debug=bool(getattr(settings, "debug", False)) if settings is not None else False,
        )
        self.models = ModelManager(settings=settings)
        self.personality = load_personality(settings=settings)
        self._engines: dict[str, TTSEngine] = dict(engines) if engines is not None else {}
        self._asr = asr
        self._capture = capture
        self._playback = playback
        self.engine: VoiceConversationEngine | None = None
        self._started = False
        self._actions = 0
        self.device = resolve_device(settings)
        self._wake: WakeWordListener | None = None
        self._ui_server: VoiceStatusServer | None = None
        self._warmup_task: asyncio.Task[None] | None = None

    async def warmup(self) -> None:
        """Preload ASR and TTS backends so the first wake turn feels instant."""
        if not bool(voice_flag(self.settings, "voice_preload_models", True)):
            return
        tasks: list[Any] = []
        if self._asr is not None:
            tasks.append(self._asr.load())
        # BanglaASR loads lazily when auto-detect confirms Bengali — avoids slow startup
        # and prevents transformers noise on Hinglish/English sessions.
        kokoro = self._engines.get("kokoro")
        if kokoro is not None and kokoro.available():
            load = getattr(kokoro, "load", None)
            if load is not None:
                tasks.append(load(language="en"))
        indicf5 = self._all_engines.get("indicf5") if hasattr(self, "_all_engines") else self._engines.get("indicf5")
        if indicf5 is not None and indicf5.available() and bool(
            voice_flag(self.settings, "tts_enable_indicf5", False)
        ):
            load = getattr(indicf5, "load", None)
            if load is not None:
                tasks.append(load(language="hi"))
        if not tasks:
            return
        results = await asyncio.gather(*tasks, return_exceptions=True)
        if self.logger is not None:
            for result in results:
                if isinstance(result, Exception):
                    self.logger.warning("voice warmup partial failure", error=str(result))

    async def ensure_warm(self) -> None:
        """Wait for background model preload started at runtime start."""
        if self._warmup_task is None:
            return
        task = self._warmup_task
        self._warmup_task = None
        try:
            await task
        except Exception as exc:
            if self.logger is not None:
                self.logger.warning("voice warmup failed", error=str(exc))

    async def start(self) -> None:
        if self._started:
            return
        if not self._engines:
            device = self.device
            registered: dict[str, TTSEngine] = {
                "voicebox": VoiceboxTTS(settings=self.settings),  # type: ignore[dict-item]
                "kokoro": KokoroTTS(),  # type: ignore[dict-item]
                "indicf5": IndicF5TTS(settings=self.settings, device=device),  # type: ignore[dict-item]
                "chatterbox": ChatterboxTTS(device=device),  # type: ignore[dict-item]
            }
            self._all_engines = registered
            self._engines = enabled_backends(self.settings, registered)
        else:
            self._engines = enabled_backends(self.settings, self._engines)
            if not hasattr(self, "_all_engines") or not self._all_engines:
                self._all_engines = dict(self._engines)
        self.models.bind_engines(self._engines)
        playback = self._playback or AudioPlayback()
        capture = self._capture or AudioCapture()
        asr_device = "cuda" if self.device == "cuda" else "cpu"
        bangla = BanglaASR(settings=self.settings, device=asr_device)
        asr = self._asr or FasterWhisperASR(settings=self.settings, device=asr_device, bangla=bangla)
        self._asr = asr
        self.engine = VoiceConversationEngine(
            settings=self.settings,
            engines=self._engines,
            all_engines=getattr(self, "_all_engines", self._engines),
            asr=asr,
            capture=capture,
            playback=playback,
            provider_router=self.provider_router,
            personality=self.personality,
            metrics=self.metrics,
            logger=self.logger,
        )
        self._started = True
        if bool(voice_flag(self.settings, "voice_preload_models", True)):
            self._warmup_task = asyncio.create_task(self.warmup(), name="voice-warmup")
        if self.logger is not None:
            self.logger.info(
                "voice runtime started",
                backends={k: v.available() for k, v in self._engines.items()},
                device=self.device,
            )

    async def stop(self) -> None:
        if self._warmup_task is not None:
            self._warmup_task.cancel()
            try:
                await self._warmup_task
            except asyncio.CancelledError:
                pass
            self._warmup_task = None
        if self._wake is not None:
            await self._wake.stop()
        if self._ui_server is not None:
            self._ui_server.stop()
            self._ui_server = None
        keep_warm = bool(voice_flag(self.settings, "voice_keep_models_warm", True))
        if self.engine is not None and not keep_warm:
            for eng in self.engine.engines.values():
                unload = getattr(eng, "unload", None)
                if unload is not None:
                    try:
                        await unload()
                    except Exception:
                        pass
            if self.engine.asr is not None:
                try:
                    await self.engine.asr.unload()
                except Exception:
                    pass
        self.engine = None
        self._started = False

    def _require_started(self) -> VoiceConversationEngine:
        if not self._started or self.engine is None:
            raise BackendUnavailableError("voice runtime not started")
        return self.engine

    async def status(self) -> VoiceStatus:
        backends = {name: eng.available() for name, eng in self._engines.items()}
        state = self.engine.state if self.engine is not None else VoiceTurnState.IDLE
        return VoiceStatus(
            enabled=self.policy.enabled,
            started=self._started,
            state=state,
            backends=backends,
            hardware=detect_hardware(),
            metrics=self.metrics.snapshot(),
            metadata={"actions": self._actions, "device": self.device},
        )

    async def speak(self, text: str, *, play: bool = True) -> SpeechPlan:
        self.policy.require_voice()
        engine = self._require_started()
        plan = await engine.speak_text(text, play=play)
        await self._emit("voice.speak", {"chars": len(text), "backend": plan.tts_backend})
        return plan

    async def listen_once(self, *, duration_s: float = 3.0) -> str:
        self.policy.require_voice()
        engine = self._require_started()
        transcript = await engine.listen_once(duration_s=duration_s)
        await self._emit("voice.listen", {"chars": len(transcript)})
        return transcript

    async def converse_turn(
        self,
        *,
        duration_s: float = 10.0,
        play: bool = True,
        on_status: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        self.policy.require_voice()
        engine = self._require_started()
        result = await engine.converse_turn(
            duration_s=duration_s,
            play=play,
            on_status=on_status,
        )
        await self._emit("voice.converse", {"state": result.get("state")})
        return result

    async def barge_in(self) -> dict[str, Any]:
        self.policy.require_voice()
        engine = self._require_started()
        await engine.barge_in.trigger()
        await self._emit("voice.barge_in", {"state": engine.state.value})
        return {"state": engine.state.value, "interrupted": True}

    def metrics_snapshot(self) -> dict[str, Any]:
        return self.metrics.snapshot().model_dump(mode="json")

    def wake_listener(self, *, on_status: Callable[[str], None] | None = None) -> WakeWordListener:
        if self._wake is None:
            asr = self._asr
            if asr is None and self.engine is not None:
                asr = self.engine.asr
            self._wake = WakeWordListener(settings=self.settings, asr=asr, on_status=on_status)
        elif on_status is not None:
            self._wake.on_status = on_status
        return self._wake

    async def wait_for_wake_word(self, *, on_status: Callable[[str], None] | None = None) -> WakeWordHit:
        self.policy.require_voice()
        self._require_started()
        await self.ensure_warm()
        return await self.wake_listener(on_status=on_status).wait_once()

    async def run_wake_loop(
        self,
        *,
        on_wake: Any | None = None,
        on_status: Callable[[str], None] | None = None,
        converse: bool = True,
        play: bool = True,
    ) -> None:
        """Continuous wake-word loop: detect phrase → optional converse turn."""
        self.policy.require_voice()
        engine = self._require_started()
        listener = self.wake_listener(on_status=on_status)
        if not listener.enabled():
            raise BackendUnavailableError(
                "wake word loop unavailable — set EMILY_VOICE_WAKE_WORD_ENABLED=true and install "
                "emily-voice[asr,audio] (ASR phrase mode) or openwakeword + EMILY_VOICE_WAKE_WORD_MODEL",
            )

        await self.ensure_warm()
        if on_status is not None:
            on_status("Voice models ready.")

        async def _on_hit(hit: WakeWordHit) -> None:
            if self.logger is not None:
                self.logger.info(
                    "voice.wake_word",
                    phrase=hit.phrase,
                    backend=hit.backend.value,
                    score=hit.score,
                )
            if on_wake is not None:
                await on_wake(hit)
            if converse and engine is not None:
                followup = await resolve_wake_question(
                    engine.asr,
                    hit,
                    on_status=on_status,
                )
                if followup.strip():
                    if on_status is not None:
                        on_status(f"Using question from wake utterance: {followup!r}")
                    await engine.process_transcript(
                        followup,
                        play=play,
                        on_status=on_status,
                    )
                else:
                    if on_status is not None:
                        on_status("Wake detected. Ask your question now (you have ~10 seconds).")
                    await engine.converse_turn(play=play, on_status=on_status)

        listener.on_detected = _on_hit
        await listener.prepare()
        await listener.run_loop()

    def start_ui_server(self, *, port: int | None = None) -> VoiceStatusServer:
        """Expose GET /voice/status for Tauri/React desktop UI."""
        if self._ui_server is None:
            bind_port = port or int(getattr(self.settings, "voice_ui_port", 8765) or 8765)
            self._ui_server = VoiceStatusServer(port=bind_port)
        self._ui_server.bind(self)
        self._ui_server.start()
        return self._ui_server

    def model_status(self, name: str | None = None) -> list[dict[str, Any]]:
        return [m.model_dump(mode="json") for m in self.models.status(name)]

    def stats(self) -> dict[str, Any]:
        return {
            "started": self._started,
            "voice_enabled": self.policy.enabled,
            "actions": self._actions,
            "backends": {k: v.available() for k, v in self._engines.items()},
            "state": self.engine.state.value if self.engine else VoiceTurnState.IDLE.value,
            "device": self.device,
        }

    async def _emit(self, event: str, payload: dict[str, Any]) -> None:
        self._actions += 1
        if self.logger is not None:
            self.logger.info(event, **payload)
        if self.event_bus is None:
            return
        await self.event_bus.publish(event, payload, source="voice")
