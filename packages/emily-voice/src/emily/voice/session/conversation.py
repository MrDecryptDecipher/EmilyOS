"""Voice conversation engine."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from typing import Any

from emily.providers.errors import ProviderInvocationError, ProviderUnavailableError
from emily.voice.adaptation import UserAdaptation
from emily.voice.asr.whisper import FasterWhisperASR
from emily.voice.audio.capture import AudioCapture
from emily.voice.audio.interruption import InterruptionController
from emily.voice.audio.playback import AudioPlayback
from emily.voice.audio.processing import postprocess_for_playback, silence_for_pause
from emily.voice.errors import BackendUnavailableError, VoiceInterruptedError
from emily.voice.language import LanguageDetector
from emily.voice.metrics import VoiceMetrics
from emily.voice.models import AudioChunk, SpeechPlan, VoiceTurnState
from emily.voice.personality import DEFAULT_PERSONALITY, VoicePersonality, load_personality
from emily.voice.session.barge_in import BargeInHandler
from emily.voice.session.barge_monitor import BargeInMonitor
from emily.voice.session.turn_taking import TurnTakingController
from emily.voice.settings_bridge import voice_flag
from emily.voice.speech.director import SpeechDirector
from emily.voice.speech.spoken_policy import spoken_system_prompt
from emily.voice.tts.base import TTSEngine
from emily.voice.tts.router import select_tts_backend
from emily.voice.vad import create_vad

_SENTENCE_END = re.compile(r"[.!?…](?:\s|$)|[\n\r]")
_SENTENCE_LEN_THRESHOLD = 320


def buffer_sentences(
    token: str,
    buffer: str,
    *,
    length_threshold: int = _SENTENCE_LEN_THRESHOLD,
) -> tuple[list[str], str]:
    """
    Append token to buffer and yield completed sentences.

    Completes on `.!?` / newline or when buffer exceeds length_threshold at a space.
    """
    buf = buffer + token
    completed: list[str] = []
    while True:
        m = _SENTENCE_END.search(buf)
        if m:
            end = m.end()
            piece = buf[:end].strip()
            buf = buf[end:]
            if piece:
                completed.append(piece)
            continue
        if len(buf) >= length_threshold:
            # Break at last whitespace when possible
            cut = buf.rfind(" ", 0, length_threshold + 1)
            if cut <= 0:
                cut = length_threshold
            piece = buf[:cut].strip()
            buf = buf[cut:].lstrip()
            if piece:
                completed.append(piece)
            continue
        break
    return completed, buf


class VoiceConversationEngine:
    """listen → ASR → LLM stream → Speech Director → TTS sentence stream → play."""

    def __init__(
        self,
        *,
        settings: Any | None = None,
        engines: Mapping[str, TTSEngine] | None = None,
        asr: FasterWhisperASR | None = None,
        capture: AudioCapture | None = None,
        playback: AudioPlayback | None = None,
        provider_router: Any | None = None,
        personality: VoicePersonality | None = None,
        metrics: VoiceMetrics | None = None,
        logger: Any | None = None,
        adaptation: UserAdaptation | None = None,
    ) -> None:
        self.settings = settings
        self.engines: dict[str, TTSEngine] = dict(engines or {})
        self.asr = asr or FasterWhisperASR(settings=settings)
        self.capture = capture or AudioCapture()
        self.playback = playback or AudioPlayback()
        self.provider_router = provider_router
        self.personality = personality or load_personality(settings=settings)
        self.metrics = metrics or VoiceMetrics(logger=logger)
        self.logger = logger
        self.director = SpeechDirector(settings=settings)
        self.language = LanguageDetector()
        self.turns = TurnTakingController()
        self.interruption = InterruptionController(self.playback)
        self.barge_in = BargeInHandler(self.turns, self.interruption, self.metrics)
        self.adaptation = adaptation or UserAdaptation(settings=settings)
        prefer_energy = bool(voice_flag(settings, "voice_prefer_energy_vad", False))
        self.vad = create_vad(prefer_silero=not prefer_energy, settings=settings)
        self.barge_monitor = BargeInMonitor(
            turns=self.turns,
            barge_in=self.barge_in,
            capture=self.capture,
            vad=self.vad,
            settings=settings,
        )
        self._pinned_backend: str | None = None

    def _language_for_speech(self, text: str) -> Any:
        """
        TTS language from reply text + user context.

        Whisper often labels Roman Hindi as ``en``; reply heuristics must win so
        Kokoro uses the Hindi voice (``hf_beta``) instead of American English.
        """
        reply = self.language.detect(text)
        user = self._current_language_state()
        reply_dom = (reply.dominant or "en").split("-")[0].lower()
        user_dom = (user.dominant or "en").split("-")[0].lower()

        if reply_dom != "en" or reply.code_switching:
            if reply_dom == "hi":
                return reply.model_copy(update={"code_switching": False, "secondary": None})
            return reply

        if user_dom not in {"", "en"}:
            return user.model_copy(update={"code_switching": False, "secondary": "en"})

        return reply

    def _current_language_state(self) -> Any:
        state = self.language.state
        detected_language = getattr(self.asr, "last_detected_language", None)
        if not detected_language:
            return state
        return state.model_copy(
            update={
                "dominant": detected_language,
                "detected_language": detected_language,
                "user_language_preference": detected_language,
            }
        )

    @property
    def state(self) -> VoiceTurnState:
        return self.turns.state

    def _active_personality(self) -> VoicePersonality:
        base = self.personality or DEFAULT_PERSONALITY
        if bool(voice_flag(self.settings, "voice_adaptive_pacing", True)) or bool(
            voice_flag(self.settings, "voice_emotion", True)
        ):
            return self.adaptation.apply_to_personality(base)
        return base

    def _listen_chunk_s(self, duration_s: float) -> float:
        raw = float(voice_flag(self.settings, "voice_listen_chunk_s", duration_s) or duration_s)
        return max(4.0, min(raw, 15.0))

    def _asr_language_hint(self) -> str | None:
        from emily.voice.asr.language_pick import detect_language_hint_from_text

        detected = getattr(self.asr, "last_detected_language", None)
        if detected and detected.split("-")[0].lower() not in {"", "en", "auto"}:
            return detected.split("-")[0].lower()
        dom = self.language.state.dominant
        if dom and dom.split("-")[0].lower() not in {"", "en"}:
            return dom.split("-")[0].lower()
        pref = self.adaptation.profile.preferred_language
        if pref and pref.split("-")[0].lower() not in {"", "en"}:
            return pref.split("-")[0].lower()
        return None

    def _tts_stream_sentences(self) -> bool:
        # Default off: one full spoken reply feels more human than choppy sentence TTS.
        if not bool(voice_flag(self.settings, "voice_tts_stream_sentences", False)):
            return False
        lang = (getattr(self.language.state, "dominant", None) or "").split("-")[0].lower()
        if lang in {"hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or", "as"}:
            return False
        return True

    async def listen_once(
        self,
        *,
        duration_s: float = 10.0,
        on_status: Callable[[str], None] | None = None,
    ) -> str:
        def status(message: str) -> None:
            if on_status is not None:
                on_status(message)

        self.turns.begin_listen()
        self.interruption.reset()
        chunk_s = self._listen_chunk_s(duration_s)
        prefer_energy = bool(voice_flag(self.settings, "voice_prefer_energy_vad", False))
        try:
            audio: AudioChunk
            vad_ms: float | None = None
            status(f"Listening for your question ({chunk_s:.0f}s — speak naturally)...")
            # Fixed window first (reliable on Windows quiet mics); trim afterward.
            t0 = time.perf_counter()
            audio = await self.capture.record(duration_s=chunk_s)
            if prefer_energy and audio.samples:
                try:
                    from emily.voice.audio.capture import segment_pcm_utterance
                    import numpy as np

                    arr = np.asarray(audio.samples, dtype=np.float32).reshape(-1)
                    trimmed, trim_vad_ms = segment_pcm_utterance(
                        arr,
                        sample_rate=audio.sample_rate,
                        vad=self.vad,
                        silence_ms=450,
                        max_duration_s=chunk_s,
                        channels=audio.channels,
                    )
                    min_samples = int(audio.sample_rate * 0.35)
                    if trimmed.size >= min_samples:
                        audio = AudioChunk(
                            samples=trimmed.tolist(),
                            sample_rate=audio.sample_rate,
                            channels=audio.channels,
                            backend=audio.backend,
                            metadata={
                                **(audio.metadata or {}),
                                "vad_latency_ms": trim_vad_ms,
                                "trimmed": True,
                            },
                        )
                        vad_ms = trim_vad_ms
                except Exception:
                    vad_ms = (time.perf_counter() - t0) * 1000.0
            else:
                vad_ms = (time.perf_counter() - t0) * 1000.0

            if vad_ms is not None:
                self.metrics.record_vad(vad_ms)

            self.turns.begin_process()
            status("Transcribing your speech...")
            t1 = time.perf_counter()
            transcript = await self.asr.transcribe(
                audio,
                language_hint=self._asr_language_hint(),
                on_status=on_status,
            )
            asr_s = time.perf_counter() - t1
            self.metrics.record_asr(asr_s * 1000.0)
            n_samples = len(audio.samples) if isinstance(audio.samples, list) else 0
            min_samples = int(self.capture.sample_rate * 0.25)
            if n_samples < min_samples:
                status("No usable microphone audio captured.")
                self.turns.idle()
                return ""
            audio_dur = n_samples / max(audio.sample_rate, 1)
            self.metrics.record_asr_rtf(asr_s, audio_dur)
            self.language.update(
                transcript,
                user_language_preference=self.adaptation.profile.preferred_language,
            )
            detected_language = getattr(self.asr, "last_detected_language", None)
            if detected_language:
                self.language.state = self.language.state.model_copy(
                    update={
                        "dominant": detected_language,
                        "detected_language": detected_language,
                        "user_language_preference": detected_language,
                    }
                )
                self.adaptation.profile.preferred_language = detected_language
            if bool(voice_flag(self.settings, "voice_adaptive_pacing", True)) or bool(
                voice_flag(self.settings, "voice_emotion", True)
            ):
                self.adaptation.observe_user_turn(transcript)
            self.metrics.log_event("voice.listen", transcript=transcript)
            if transcript.strip():
                det = getattr(self.asr, "last_detected_language", None)
                prob = getattr(self.asr, "last_language_probability", None)
                prob_s = f" ({prob:.0%})" if prob is not None else ""
                lang_s = f" [{det}{prob_s}]" if det else ""
                status(f"You said{lang_s}: {transcript.strip()!r}")
            else:
                status("Could not understand speech (empty transcript).")
            self.turns.idle()
            return transcript
        except Exception:
            self.turns.error()
            raise

    async def listen_for_question(
        self,
        *,
        duration_s: float = 10.0,
        on_status: Callable[[str], None] | None = None,
        max_attempts: int = 3,
    ) -> str:
        for attempt in range(1, max_attempts + 1):
            if attempt > 1 and on_status is not None:
                on_status(f"Retrying listen ({attempt}/{max_attempts})...")
            transcript = await self.listen_once(duration_s=duration_s, on_status=on_status)
            if transcript.strip():
                return transcript.strip()
        return ""

    async def _play_chunk(self, chunk: AudioChunk, *, pace: float = 1.0) -> bool:
        # Never slow-stretch playback (drops pitch → half-male). Keep near 1.0.
        safe_pace = 1.0 if pace < 0.98 else min(1.06, float(pace))
        pitch_up = 0.0
        backend = (chunk.backend or "").lower()
        if backend == "kokoro":
            pitch_up = 0.35  # subtle younger lift — keep tiny to avoid chipmunk/panic
        processed = postprocess_for_playback(chunk, pace=safe_pace, pitch_semitones=pitch_up)
        return await self.playback.play(processed)

    async def speak_plan(
        self,
        plan: SpeechPlan,
        *,
        play: bool = True,
        on_status: Callable[[str], None] | None = None,
    ) -> tuple[SpeechPlan, list[AudioChunk]]:
        def status(message: str) -> None:
            if on_status is not None:
                on_status(message)

        self.turns.begin_speak()
        self.interruption.reset()
        self.metrics.begin_turn()
        available = [n for n, e in self.engines.items() if e.available()]
        if not available and self.engines:
            raise BackendUnavailableError("no TTS backends available", details={"registered": list(self.engines)})
        if not self.engines:
            raise BackendUnavailableError("no TTS engines configured")

        backend_name = select_tts_backend(
            plan, self.engines, pinned=self._pinned_backend, settings=self.settings
        )
        if not (plan.segments and len({s.language for s in plan.segments if s.language}) > 1):
            self._pinned_backend = backend_name
        engine = self.engines[backend_name]
        plan = plan.model_copy(update={"tts_backend": backend_name})
        if backend_name == "kokoro":
            status("Speaking (Kokoro — fast)...")
        elif backend_name == "indicf5":
            status("Speaking (IndicF5 — natural Hindi/Indic)...")
        elif backend_name == "voicebox":
            status("Speaking (Voicebox — soft preset voice)...")
        else:
            status(f"Speaking ({backend_name})...")

        monitor_task = self.barge_monitor.start() if play else None
        chunks: list[AudioChunk] = []
        t0 = time.perf_counter()
        audio_duration = 0.0
        # Playback pace must stay ~1.0 — slower stretch drops pitch (sounds male).
        playback_pace = 1.0
        multi_lang = bool(
            plan.segments
            and len({s.language for s in plan.segments if s.language}) > 1
        )
        try:
            texts = plan.segments if plan.segments else None
            if (
                texts
                and not multi_lang
                and hasattr(engine, "synthesize_stream")
                and engine.capabilities.streaming
            ):
                async for chunk in engine.synthesize_stream(plan):  # type: ignore[misc]
                    self.interruption.raise_if_interrupted()
                    chunks.append(chunk)
                    audio_duration += len(chunk.samples) / max(chunk.sample_rate, 1) if isinstance(chunk.samples, list) else 0.0
                    self.metrics.mark_first_audio()
                    if play:
                        ok = await self._play_chunk(chunk, pace=playback_pace)
                        if not ok:
                            raise VoiceInterruptedError()
            elif texts:
                for segment in texts:
                    self.interruption.raise_if_interrupted()
                    seg_lang = (segment.language or plan.language).split("-")[0].lower()
                    seg_plan = plan.model_copy(
                        update={
                            "text": segment.text,
                            "segments": [segment],
                            "language": seg_lang,
                            "code_switching": plan.code_switching,
                        }
                    )
                    seg_backend = select_tts_backend(
                        seg_plan,
                        self.engines,
                        pinned=self._pinned_backend,
                        settings=self.settings,
                    )
                    self._pinned_backend = seg_backend
                    seg_engine = self.engines[seg_backend]
                    seg_plan = seg_plan.model_copy(update={"tts_backend": seg_backend})
                    chunk = await seg_engine.synthesize(seg_plan)
                    chunks.append(chunk)
                    audio_duration += len(chunk.samples) / max(chunk.sample_rate, 1) if isinstance(chunk.samples, list) else 0.0
                    self.metrics.mark_first_audio()
                    if play:
                        ok = await self._play_chunk(chunk, pace=playback_pace)
                        if not ok:
                            raise VoiceInterruptedError()
                        pause = silence_for_pause(segment.pause_after, sample_rate=chunk.sample_rate)
                        if pause.size and play:
                            await self._play_chunk(
                                AudioChunk(
                                    samples=pause.tolist(),
                                    sample_rate=chunk.sample_rate,
                                    channels=1,
                                    backend="silence",
                                ),
                                pace=1.0,
                            )
            else:
                chunk = await engine.synthesize(plan)
                chunks.append(chunk)
                audio_duration += len(chunk.samples) / max(chunk.sample_rate, 1) if isinstance(chunk.samples, list) else 0.0
                self.metrics.mark_first_audio()
                if play:
                    ok = await self._play_chunk(chunk)
                    if not ok:
                        raise VoiceInterruptedError()

            gen_s = time.perf_counter() - t0
            self.metrics.record_tts(gen_s * 1000.0, backend=backend_name)
            self.metrics.record_tts_rtf(gen_s, audio_duration)
            self.metrics.record_memory()
            self.metrics.record_turn()
            self.turns.idle()
            self._pinned_backend = None
            if bool(voice_flag(self.settings, "voice_adaptive_pacing", True)) or bool(
                voice_flag(self.settings, "voice_emotion", True)
            ):
                self.adaptation.observe_reply(plan.text)
            return plan, chunks
        except VoiceInterruptedError:
            self.turns.interrupt()
            self.metrics.record_barge_in()
            if bool(voice_flag(self.settings, "voice_adaptive_pacing", True)) or bool(
                voice_flag(self.settings, "voice_emotion", True)
            ):
                self.adaptation.observe_interrupt()
            raise
        except Exception:
            self.turns.error()
            self.metrics.record_error("tts_failed", tags={"backend": backend_name})
            raise
        finally:
            if monitor_task is not None:
                await self.barge_monitor.stop()

    async def speak_text(
        self,
        text: str,
        *,
        play: bool = True,
        on_status: Callable[[str], None] | None = None,
    ) -> SpeechPlan:
        lang = self._language_for_speech(text) if text else self.language.state
        available = [n for n, e in self.engines.items() if e.available()]
        plan = self.director.plan(
            text,
            language_state=lang,
            personality=self._active_personality(),
            available_backends=available or list(self.engines),
            settings=self.settings,
        )
        final_plan, _chunks = await self.speak_plan(plan, play=play, on_status=on_status)
        return final_plan

    async def _llm_stream(
        self,
        transcript: str,
        *,
        on_status: Callable[[str], None] | None = None,
    ) -> str:
        parts: list[str] = []
        async for sentence in self._llm_sentence_stream(transcript, on_status=on_status):
            parts.append(sentence)
        return " ".join(parts).strip()

    async def _llm_sentence_stream(
        self,
        transcript: str,
        *,
        on_status: Callable[[str], None] | None = None,
    ) -> AsyncIterator[str]:
        """Yield complete sentences as LLM tokens arrive."""
        def status(message: str) -> None:
            if on_status is not None:
                on_status(message)

        router = self.provider_router
        if router is None:
            status("No LLM provider configured; echoing transcript.")
            yield transcript
            return
        messages: Sequence[Mapping[str, Any]] = [
            {"role": "system", "content": spoken_system_prompt()},
            {
                "role": "system",
                "content": (
                    f"Detected user language: {self._current_language_state().dominant}. "
                    "Reply in that language unless the user explicitly asks for another one. "
                    "For Hindi, you MUST write in Devanagari script (हिंदी), never Roman Hinglish."
                ),
            },
            {"role": "user", "content": transcript},
        ]
        t0 = time.perf_counter()
        self.turns.begin_think()
        primary = getattr(router, "primary", "llm")
        backup = getattr(router, "backup", None)
        status(f"Thinking... (LLM: {primary}" + (f", backup: {backup}" if backup else "") + ")")
        buffer = ""
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        pump_error: list[BaseException] = []
        got_token = False
        llm_timeout = float(voice_flag(self.settings, "voice_llm_timeout_seconds", 45) or 45)

        async def _pump_stream() -> None:
            nonlocal got_token
            try:
                stream = router.stream(messages)
                if hasattr(stream, "__aiter__"):
                    async for chunk in stream:
                        self.interruption.raise_if_interrupted()
                        if not got_token:
                            got_token = True
                            status(f"LLM replying ({round(time.perf_counter() - t0, 1)}s)...")
                        await queue.put(str(chunk))
                else:
                    result = await stream if isinstance(stream, Awaitable) else stream
                    got_token = True
                    await queue.put(str(result))
            except asyncio.CancelledError:
                raise
            except VoiceInterruptedError:
                raise
            except (ProviderInvocationError, ProviderUnavailableError) as exc:
                pump_error.append(exc)
            except Exception as exc:
                pump_error.append(exc)
            finally:
                await queue.put(None)

        pump_task = asyncio.create_task(_pump_stream(), name="voice-llm-stream")
        self.interruption.arm_generation(pump_task)
        deadline = time.perf_counter() + llm_timeout
        try:
            while True:
                self.interruption.raise_if_interrupted()
                remaining = deadline - time.perf_counter()
                if remaining <= 0 and not got_token:
                    status("LLM is taking too long — cancelling request.")
                    pump_task.cancel()
                    pump_error.append(
                        ProviderUnavailableError(
                            "LLM response timed out",
                            provider=str(primary),
                        )
                    )
                    break
                try:
                    chunk = await asyncio.wait_for(queue.get(), timeout=min(5.0, max(0.1, remaining)))
                except asyncio.TimeoutError:
                    if not got_token:
                        status(f"Still waiting for LLM ({round(time.perf_counter() - t0, 0):.0f}s)...")
                    continue
                if chunk is None:
                    self.interruption.raise_if_interrupted()
                    break
                completed, buffer = buffer_sentences(chunk, buffer)
                for sentence in completed:
                    status(f"Reply: {sentence!r}")
                    yield sentence
            if pump_error:
                exc = pump_error[0]
                if isinstance(exc, (ProviderInvocationError, ProviderUnavailableError)):
                    status(f"LLM unavailable ({exc}).")
                    yield (
                        "Sorry, I could not reach the language model right now. "
                        "Please try again in a moment."
                    )
                else:
                    raise exc
            tail = buffer.strip()
            if tail:
                yield tail
            self.metrics.record_llm((time.perf_counter() - t0) * 1000.0)
        except VoiceInterruptedError:
            if not pump_task.done():
                pump_task.cancel()
                try:
                    await pump_task
                except (asyncio.CancelledError, Exception):
                    pass
            raise
        finally:
            self.interruption.arm_generation(None)
            if not pump_task.done():
                pump_task.cancel()
                try:
                    await pump_task
                except (asyncio.CancelledError, Exception):
                    pass

    async def converse_streaming(
        self,
        *,
        duration_s: float = 10.0,
        play: bool = True,
        on_status: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Listen once, then TTS each sentence as the LLM streams."""
        def status(message: str) -> None:
            if on_status is not None:
                on_status(message)

        self.metrics.begin_turn()
        status("Starting conversation turn...")
        transcript = await self.listen_for_question(duration_s=duration_s, on_status=on_status)
        if not transcript.strip():
            fallback = (
                "I heard the wake phrase, but I didn't catch your question. "
                "Try saying: Hey Emily, then your question in the same breath."
            )
            status(fallback)
            if play:
                await self.speak_text(fallback, play=True, on_status=on_status)
            self.metrics.record_e2e()
            return {
                "transcript": "",
                "reply": fallback,
                "plan": None,
                "state": self.state.value,
                "metrics": self.metrics.snapshot().model_dump(mode="json"),
            }
        replies: list[str] = []
        last_plan: SpeechPlan | None = None
        interrupted = False
        stream_tts = self._tts_stream_sentences()
        try:
            if stream_tts:
                async for sentence in self._llm_sentence_stream(transcript, on_status=on_status):
                    self.interruption.raise_if_interrupted()
                    replies.append(sentence)
                    status("Speaking...")
                    try:
                        last_plan = await self.speak_text(sentence, play=play, on_status=on_status)
                    except VoiceInterruptedError:
                        interrupted = True
                        status("Interrupted.")
                        break
                    if self.interruption.interrupted:
                        interrupted = True
                        break
            else:
                status("Thinking...")
                async for sentence in self._llm_sentence_stream(transcript, on_status=on_status):
                    self.interruption.raise_if_interrupted()
                    replies.append(sentence)
                reply_text = " ".join(replies).strip()
                if reply_text:
                    status("Speaking...")
                    last_plan = await self.speak_text(reply_text, play=play, on_status=on_status)
        except VoiceInterruptedError:
            interrupted = True
            status("Interrupted.")
        reply = " ".join(replies).strip()
        if interrupted and not reply.strip():
            reply = ""
        self.metrics.record_e2e()
        status("Conversation turn complete.")
        return {
            "transcript": transcript,
            "reply": reply,
            "plan": last_plan.model_dump(mode="json") if last_plan else None,
            "state": self.state.value,
            "metrics": self.metrics.snapshot().model_dump(mode="json"),
        }

    async def converse_turn(
        self,
        *,
        duration_s: float = 10.0,
        play: bool = True,
        on_status: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        if bool(voice_flag(self.settings, "voice_streaming", True)):
            return await self.converse_streaming(
                duration_s=duration_s,
                play=play,
                on_status=on_status,
            )
        def status(message: str) -> None:
            if on_status is not None:
                on_status(message)

        self.metrics.begin_turn()
        status("Starting conversation turn...")
        transcript = await self.listen_once(duration_s=duration_s, on_status=on_status)
        reply = await self._llm_stream(transcript, on_status=on_status)
        status("Speaking...")
        plan = await self.speak_text(reply, play=play, on_status=on_status)
        self.metrics.record_e2e()
        status("Conversation turn complete.")
        return {
            "transcript": transcript,
            "reply": reply,
            "plan": plan.model_dump(mode="json"),
            "state": self.state.value,
            "metrics": self.metrics.snapshot().model_dump(mode="json"),
        }

    async def process_transcript(
        self,
        transcript: str,
        *,
        play: bool = True,
        on_status: Callable[[str], None] | None = None,
        llm: Callable[[str], Awaitable[str]] | None = None,
    ) -> dict[str, Any]:
        def status(message: str) -> None:
            if on_status is not None:
                on_status(message)

        self.metrics.begin_turn()
        status("Starting conversation turn...")
        self.language.update(transcript)
        detected_language = getattr(self.asr, "last_detected_language", None)
        if detected_language:
            self.language.state = self.language.state.model_copy(
                update={
                    "dominant": detected_language,
                    "detected_language": detected_language,
                    "user_language_preference": detected_language,
                }
            )
        if bool(voice_flag(self.settings, "voice_adaptive_pacing", True)) or bool(
            voice_flag(self.settings, "voice_emotion", True)
        ):
            self.adaptation.observe_user_turn(transcript)
        if llm is not None:
            self.turns.begin_think()
            reply = await llm(transcript)
            plan = await self.speak_text(reply, play=play, on_status=on_status)
        elif bool(voice_flag(self.settings, "voice_streaming", True)):
            replies: list[str] = []
            plan = None
            if self._tts_stream_sentences():
                async for sentence in self._llm_sentence_stream(transcript, on_status=on_status):
                    replies.append(sentence)
                    status("Speaking...")
                    plan = await self.speak_text(sentence, play=play, on_status=on_status)
            else:
                async for sentence in self._llm_sentence_stream(transcript, on_status=on_status):
                    replies.append(sentence)
                reply = " ".join(replies).strip()
                if reply:
                    status("Speaking...")
                    plan = await self.speak_text(reply, play=play, on_status=on_status)
                replies = [reply] if reply else []
            reply = " ".join(replies).strip()
            if plan is None and reply:
                plan = await self.speak_text(reply, play=play, on_status=on_status)
        else:
            reply = await self._llm_stream(transcript)
            plan = await self.speak_text(reply, play=play, on_status=on_status)
        self.metrics.record_e2e()
        return {"transcript": transcript, "reply": reply, "plan": plan.model_dump(mode="json")}
