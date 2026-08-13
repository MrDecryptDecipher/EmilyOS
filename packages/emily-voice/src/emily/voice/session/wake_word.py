"""Continuous wake-word listener — openWakeWord and/or ASR phrase match."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

from emily.voice.asr.whisper import FasterWhisperASR
from emily.voice.audio.capture import AudioCapture
from emily.voice.audio.processing import chunk_has_speech, chunk_rms
from emily.voice.errors import BackendUnavailableError
from emily.voice.models import AudioChunk
from emily.voice.settings_bridge import voice_flag
from emily.voice.vad import create_vad
from emily.voice.vad.silero import EnergyVAD

_OWW_FRAME = 1280  # 80 ms @ 16 kHz (openWakeWord recommendation)
_OWW_SAMPLE_RATE = 16000


class WakeWordBackend(str, Enum):
    OPENWAKEWORD = "openwakeword"
    ASR_PHRASE = "asr_phrase"


@dataclass(frozen=True)
class WakeWordHit:
    phrase: str
    backend: WakeWordBackend
    score: float = 1.0
    transcript: str = ""
    audio: AudioChunk | None = None


def _normalize_phrase(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


# ASR often hears "hey" as "hry", "hi", "hai", etc. Also "Emilica", "Emilia", etc.
_HEY_EMILY_RE = re.compile(
    r"\b(hey|hry|hi|hai|aye)\s*,?\s*emil(?:y|ia|ica|i|ie)\b",
    re.IGNORECASE,
)

# Romanized Hindi / Hinglish tokens (Whisper often mis-hears these as random English).
_HINGLISH_RE = re.compile(
    r"\b("
    r"kya|kaise|kaisa|kaisi|haal|hal|chaal|chal|chahiye|chahie|karo|karna|kar|bata|bhai|"
    r"accha|achha|theek|thik|namaste|mujhe|aap|tum|hai|hoon|hun|nahi|nahin|haan|han|ji|"
    r"kal|aaj|abhi|kaam|madad|transaction|check|rahe|raha|rahi|kyaa"
    r")\b",
    re.IGNORECASE,
)


def _looks_like_hinglish(text: str) -> bool:
    return bool(_HINGLISH_RE.search(text or ""))


def _hinglish_token_count(text: str) -> int:
    return len(_HINGLISH_RE.findall(text or ""))


_SUSPICIOUS_WAKE_FOLLOWUP = re.compile(
    r"\b(where are you going|thank you|thanks for watching|you'?re welcome|subscribe)\b",
    re.IGNORECASE,
)
_CLEAR_ENGLISH_QUESTION = re.compile(
    r"^(how|what|when|where|why|who|can|could|would|will|do|does|did|is|are|am|tell)\b",
    re.IGNORECASE,
)

# English Whisper often translates Hindi/Hinglish greetings into these English phrases.
_LIKELY_HINDI_AS_ENGLISH = re.compile(
    r"\b("
    r"what'?s up|how are you|how'?s it going|what are you doing|what are you up to|"
    r"how are you doing|how have you been|how do you do|how'?s everything|"
    r"how is it going|how you doing"
    r")\b",
    re.IGNORECASE,
)


def _looks_like_translated_hindi_greeting(text: str) -> bool:
    return bool(_LIKELY_HINDI_AS_ENGLISH.search(text or ""))


def _english_followup_is_trusted(en_followup: str) -> bool:
    """English wake-path text that should not be replaced by a Hindi re-transcription."""
    from emily.voice.asr.language_pick import (
        looks_like_english_hallucination,
        looks_like_generic_english_followup,
    )

    text = (en_followup or "").strip()
    if len(text) < 2:
        return False
    # Strong roman Hinglish from English ASR is usually correct — keep it (avoid Tamil swaps).
    hinglish_hits = _hinglish_token_count(text)
    if hinglish_hits >= 2 or (hinglish_hits >= 1 and len(re.findall(r"[a-zA-Z']+", text)) >= 5):
        return True
    if hinglish_hits == 1 and len(text.split()) <= 3:
        return False
    # Greeting-style English is often a Hindi→English Whisper translation — never trust alone.
    if _looks_like_translated_hindi_greeting(text):
        return False
    words = re.findall(r"[a-zA-Z']+", text)
    if looks_like_generic_english_followup(text):
        return False
    if looks_like_english_hallucination(text, language_probability=0.45):
        return False
    if _SUSPICIOUS_WAKE_FOLLOWUP.search(text):
        return False
    # Specific factual English questions (time, weather, name) can be trusted.
    if _CLEAR_ENGLISH_QUESTION.search(text) and len(words) >= 3:
        return True
    return len(words) >= 2 and len(text) >= 5


def _english_followup_needs_retranscribe(en_followup: str) -> bool:
    """Re-transcribe wake audio when English wake ASR may have mis-heard Indic speech."""
    if not (en_followup or "").strip():
        return True
    if _looks_like_translated_hindi_greeting(en_followup):
        return True
    return not _english_followup_is_trusted(en_followup)


_GENERIC_HINGLISH_GREETING = re.compile(
    r"^(?:kya haal chaal|kaise ho|kaisa hai|kya haal hai)(?:\?|\.|!)?$",
    re.IGNORECASE,
)


def _multi_is_wrong_script_for_hinglish(multi_followup: str) -> bool:
    from emily.voice.language import script_counts

    counts = script_counts(multi_followup)
    hi = counts.get("hi", 0) + counts.get("mr", 0)
    wrong = sum(counts.get(lang, 0) for lang in ("ta", "te", "bn", "kn", "ml", "gu", "pa", "as"))
    return wrong > 0 and hi == 0


def _should_prefer_multilingual_followup(
    en_followup: str,
    multi_followup: str,
    *,
    detected_language: str | None,
) -> bool:
    if not multi_followup.strip():
        return False
    from emily.voice.asr.language_pick import (
        INDIC_ASR_CANDIDATES,
        indic_script_share,
        looks_like_english_hallucination,
        looks_like_generic_english_followup,
    )
    from emily.voice.language import script_counts

    # Never replace clear roman Hinglish with Tamil/Telugu/Bengali script hallucinations.
    if _looks_like_hinglish(en_followup) and _multi_is_wrong_script_for_hinglish(multi_followup):
        return False
    if (
        _GENERIC_HINGLISH_GREETING.match(multi_followup.strip())
        and _english_followup_is_trusted(en_followup)
    ):
        return False
    if indic_script_share(multi_followup) >= 0.05:
        if _looks_like_hinglish(en_followup) and _multi_is_wrong_script_for_hinglish(multi_followup):
            return False
        return True
    if _looks_like_hinglish(multi_followup) and not _looks_like_hinglish(en_followup):
        return True
    if detected_language in INDIC_ASR_CANDIDATES:
        if detected_language in {"ta", "te", "bn", "kn", "ml"} and _looks_like_hinglish(en_followup):
            return False
        if en_followup.strip().lower() != multi_followup.strip().lower():
            return True
    if looks_like_generic_english_followup(en_followup) and (
        _looks_like_hinglish(multi_followup) or indic_script_share(multi_followup) >= 0.05
    ):
        if _multi_is_wrong_script_for_hinglish(multi_followup):
            return _looks_like_hinglish(multi_followup)
        return True
    # Hindi spoken → English greeting translation: keep Indic/Hinglish multi when present.
    if _looks_like_translated_hindi_greeting(en_followup) and (
        _looks_like_hinglish(multi_followup) or indic_script_share(multi_followup) >= 0.05
    ):
        if _multi_is_wrong_script_for_hinglish(multi_followup):
            return _looks_like_hinglish(multi_followup)
        return True
    if looks_like_english_hallucination(en_followup, language_probability=0.45):
        return True
    counts = script_counts(multi_followup)
    if counts.get("hi", 0) + counts.get("te", 0) + counts.get("bn", 0) > 0:
        if _looks_like_hinglish(en_followup) and _multi_is_wrong_script_for_hinglish(multi_followup):
            return False
        return True
    return False


async def resolve_wake_question(
    asr: FasterWhisperASR,
    hit: WakeWordHit,
    *,
    on_status: Callable[[str], None] | None = None,
) -> str:
    """
    Extract the user's question after the wake phrase.

    Wake detection uses English ASR (reliable for "Hey Emily"). If the user continued
    in Hindi/Hinglish in the same breath, re-transcribe the same audio with multilingual
    ASR and prefer that follow-up when it looks more accurate.
    """
    en_followup = _strip_wake_phrase(hit.phrase, hit.transcript)
    if not en_followup.strip():
        return ""

    def status(msg: str) -> None:
        if on_status is not None:
            on_status(msg)

    if hit.audio is None or not _english_followup_needs_retranscribe(en_followup):
        status(f"Question: {en_followup!r}")
        return en_followup.strip()

    status("Extracting your question from wake audio...")
    from emily.voice.asr.language_pick import detect_language_hint_from_text

    lang_hint = detect_language_hint_from_text(en_followup)
    # Greeting-style English from wake ASR is usually Hindi speech — force Hindi path.
    if _looks_like_translated_hindi_greeting(en_followup) or not lang_hint:
        lang_hint = "hi"
    multi_full = await asr.transcribe_wake_followup(
        hit.audio,
        language_hint=lang_hint,
        on_status=on_status,
    )
    multi_followup = _strip_wake_phrase(hit.phrase, multi_full)
    detected = getattr(asr, "last_detected_language", None)
    if _should_prefer_multilingual_followup(
        en_followup,
        multi_followup,
        detected_language=detected,
    ):
        if multi_followup.strip():
            det = f" [{detected}]" if detected else ""
            status(f"Question{det}: {multi_followup!r}")
            return multi_followup.strip()
    status(f"Question: {en_followup!r}")
    return en_followup.strip()


def _strip_wake_phrase(phrase: str, transcript: str) -> str:
    """Return user question text after the wake phrase, if spoken in the same utterance."""
    t = _normalize_phrase(transcript)
    if not t:
        return ""
    cleaned = _HEY_EMILY_RE.sub("", t, count=1).strip(" ,.!?")
    p = _normalize_phrase(phrase)
    if p and p in t:
        cleaned = t.replace(p, "", 1).strip(" ,.!?")
    return cleaned


def _phrase_in_transcript(phrase: str, transcript: str) -> bool:
    p = _normalize_phrase(phrase)
    t = _normalize_phrase(transcript)
    if not p or not t:
        return False
    if p in t or t.startswith(p):
        return True
    # "Hey Emily" and common mis-hearings (e.g. "Hry Emily")
    if "emily" in p:
        return bool(_HEY_EMILY_RE.search(transcript))
    return False


class WakeWordListener:
    """
    Listen for a configured wake phrase.

    - If ``voice_wake_word_model`` points to an openWakeWord ONNX/TFLite model, use it.
    - Otherwise use real ASR on VAD-segmented speech to match ``wake_word`` text
      (works for custom phrases like "Emily" without training a KWS model).
    """

    def __init__(
        self,
        *,
        settings: Any | None = None,
        capture: AudioCapture | None = None,
        asr: FasterWhisperASR | None = None,
        on_detected: Callable[[WakeWordHit], Awaitable[None]] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        self.settings = settings
        self.capture = capture or AudioCapture()
        self.asr = asr or FasterWhisperASR(settings=settings)
        self.on_detected = on_detected
        self.on_status = on_status
        prefer_energy = bool(voice_flag(settings, "voice_prefer_energy_vad", False))
        if prefer_energy:
            # Match quiet laptop mics (VOICE_MIC_MIN_RMS ~0.001); too-high VAD → empty captures.
            mic_floor = float(voice_flag(settings, "voice_mic_min_rms", 0.001) or 0.001)
            self.vad = EnergyVAD(
                threshold=max(0.0015, min(0.008, mic_floor * 2.0)),
                min_speech_ms=60.0,
            )
        else:
            self.vad = create_vad(prefer_silero=True, settings=settings)
        self._oww: Any | None = None
        self._running = False
        self._task: asyncio.Task[None] | None = None

    @property
    def phrase(self) -> str:
        return str(voice_flag(self.settings, "wake_word", "Hey Emily") or "Hey Emily")

    @property
    def threshold(self) -> float:
        return float(voice_flag(self.settings, "voice_wake_word_threshold", 0.5) or 0.5)

    def enabled(self) -> bool:
        if not bool(voice_flag(self.settings, "voice_enabled", False)):
            return False
        if not bool(voice_flag(self.settings, "voice_wake_word_enabled", False)):
            return False
        return self.available()

    def available(self) -> bool:
        if self._oww_available() or self._asr_phrase_available():
            return True
        return False

    def backend(self) -> WakeWordBackend:
        if self._oww_available():
            return WakeWordBackend.OPENWAKEWORD
        return WakeWordBackend.ASR_PHRASE

    def _oww_model_path(self) -> str | None:
        path = voice_flag(self.settings, "voice_wake_word_model", None)
        return str(path).strip() if path else None

    def _oww_available(self) -> bool:
        model_path = self._oww_model_path()
        if not model_path:
            return False
        try:
            from openwakeword.model import Model  # noqa: F401

            from pathlib import Path

            return Path(model_path).is_file()
        except Exception:
            return False

    def _asr_phrase_available(self) -> bool:
        return self.capture.available() and self.asr.available() and bool(self.phrase.strip())

    def _status(self, message: str) -> None:
        if self.on_status is not None:
            self.on_status(message)

    def _listen_chunk_s(self) -> float:
        raw = float(voice_flag(self.settings, "voice_wake_word_listen_chunk_s", 7.5) or 7.5)
        return max(3.0, min(raw, 12.0))

    def _max_listen_s(self) -> float:
        raw = float(voice_flag(self.settings, "voice_wake_word_max_listen_s", 12.0) or 12.0)
        return max(4.0, min(raw, 15.0))

    def _mic_min_rms(self) -> float:
        raw = float(voice_flag(self.settings, "voice_mic_min_rms", 0.001) or 0.001)
        return max(0.0003, min(raw, 0.02))

    def _max_wake_attempts(self) -> int:
        raw = int(voice_flag(self.settings, "voice_wake_max_attempts", 15) or 15)
        return max(3, min(raw, 50))

    async def prepare(self) -> None:
        """Preload ASR weights so the first listen attempt is not a silent multi-minute stall."""
        if self._oww_available():
            return
        if getattr(self.asr, "_model", None) is not None:
            dev = getattr(self.asr, "device", "cpu")
            ct = getattr(self.asr, "compute_type", "")
            detail = f"{dev}, {ct}" if ct else dev
            self._status(f"Speech model ready ({detail}).")
            return
        self._status("Loading speech recognition model (first run can take 1–2 min)...")
        await self.asr.load()
        dev = getattr(self.asr, "device", "cpu")
        ct = getattr(self.asr, "compute_type", "")
        detail = f"{dev}, {ct}" if ct else dev
        self._status(f"Speech model ready ({detail}).")

    def _load_oww(self) -> Any:
        if self._oww is not None:
            return self._oww
        from openwakeword.model import Model

        model_path = self._oww_model_path()
        if not model_path:
            raise BackendUnavailableError("voice_wake_word_model path is not configured")
        self._oww = Model(wakeword_models=[model_path], inference_framework="onnx")
        return self._oww

    async def wait_once(self) -> WakeWordHit:
        """Block until the wake phrase is detected once."""
        if not self.enabled():
            raise BackendUnavailableError(
                "wake word listener unavailable — enable EMILY_VOICE_WAKE_WORD_ENABLED and install "
                "openwakeword + model path OR emily-voice[asr,audio] for ASR phrase mode",
            )
        if self._oww_available():
            return await self._wait_openwakeword()
        await self.prepare()
        return await self._wait_asr_phrase()

    async def run_loop(self) -> None:
        """Continuous wake → callback loop until cancelled."""
        self._running = True
        while self._running:
            hit = await self.wait_once()
            if self.on_detected is not None:
                await self.on_detected(hit)

    def start_background(self) -> asyncio.Task[None]:
        if self._task is not None and not self._task.done():
            return self._task
        self._task = asyncio.create_task(self.run_loop(), name="voice-wake-word")
        return self._task

    async def stop(self) -> None:
        self._running = False
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _wait_openwakeword(self) -> WakeWordHit:
        import sounddevice as sd

        model = self._load_oww()
        loop = asyncio.get_running_loop()
        hit: asyncio.Future[WakeWordHit] = loop.create_future()

        def callback(indata, frames, time, status) -> None:  # type: ignore[no-untyped-def]
            if hit.done():
                return
            audio = (indata.flatten() * 32767).astype(np.int16)
            prediction = model.predict(audio)
            for name, score in prediction.items():
                if float(score) >= self.threshold and not hit.done():
                    loop.call_soon_threadsafe(
                        hit.set_result,
                        WakeWordHit(phrase=self.phrase, backend=WakeWordBackend.OPENWAKEWORD, score=float(score)),
                    )
                    return

        stream = sd.InputStream(
            samplerate=_OWW_SAMPLE_RATE,
            channels=1,
            blocksize=_OWW_FRAME,
            dtype="float32",
            callback=callback,
        )
        with stream:
            while not hit.done():
                await asyncio.sleep(0.05)
        return await hit

    async def _record_wake_chunk(self) -> AudioChunk:
        """
        Fixed-window capture (reliable on Windows), then energy-trim when possible.

        Live VAD wait-for-speech often returns empty on quiet mics; recording first
        then trimming keeps responsiveness without dropping audio.
        """
        max_s = min(self._listen_chunk_s(), self._max_listen_s())
        chunk = await self.capture.record(duration_s=max_s)
        if not chunk.samples:
            return chunk
        prefer_energy = bool(voice_flag(self.settings, "voice_prefer_energy_vad", False))
        if not prefer_energy:
            return chunk
        try:
            from emily.voice.audio.capture import segment_pcm_utterance

            arr = np.asarray(chunk.samples, dtype=np.float32).reshape(-1)
            trimmed, vad_ms = segment_pcm_utterance(
                arr,
                sample_rate=chunk.sample_rate,
                vad=self.vad,
                silence_ms=400,
                max_duration_s=max_s,
                channels=chunk.channels,
            )
            min_samples = int(chunk.sample_rate * 1.8)
            # Only keep trim if it still has enough speech; else use full window
            # (aggressive trim was producing 0.4s clips → Whisper hears "you").
            if trimmed.size >= min_samples and trimmed.size >= int(arr.size * 0.45):
                meta = dict(chunk.metadata or {})
                meta["vad_latency_ms"] = vad_ms
                meta["trimmed"] = True
                return AudioChunk(
                    samples=trimmed.tolist(),
                    sample_rate=chunk.sample_rate,
                    channels=chunk.channels,
                    backend=chunk.backend,
                    metadata=meta,
                )
        except Exception:
            pass
        return chunk

    async def _wait_asr_phrase(self) -> WakeWordHit:
        """Energy-VAD or fixed mic chunks + faster-whisper phrase match (reliable on Windows)."""
        chunk_s = min(self._listen_chunk_s(), self._max_listen_s())
        attempt = 0
        max_attempts = self._max_wake_attempts()
        min_rms = self._mic_min_rms()
        self._status(
            f"Say {self.phrase!r} at a natural pace ({chunk_s:.0f}s window). "
            "Include your question in the same breath, e.g. "
            "'Hey Emily, kya haal hai?' or 'Hey Emily, what time is it?'"
        )
        while attempt < max_attempts:
            attempt += 1
            self._status(f"Wake listen attempt {attempt}/{max_attempts}: listening...")
            chunk = await self._record_wake_chunk()
            if not chunk.samples:
                self._status("No audio captured from microphone; retrying...")
                await asyncio.sleep(0.2)
                continue
            if not chunk_has_speech(chunk, min_rms=min_rms):
                self._status(
                    f"Mic level low ({chunk_rms(chunk):.4f}) — speak louder, closer to the mic."
                )
                await asyncio.sleep(0.1)
                continue
            self._status("Transcribing wake phrase...")
            transcript = await self.asr.transcribe_wake(
                chunk,
                wake_phrase=self.phrase,
                on_status=self._status,
            )
            preview = (transcript or "").strip()
            if preview:
                self._status(f"Heard: {preview!r}")
                if not _phrase_in_transcript(self.phrase, transcript):
                    self._status(
                        f"Wake phrase not matched yet — say {self.phrase!r} again "
                        "(English: 'Hey Emily' or 'Hi Emily')."
                    )
            else:
                self._status("Heard silence — try speaking louder or closer to the mic.")
            if _phrase_in_transcript(self.phrase, transcript):
                return WakeWordHit(
                    phrase=self.phrase,
                    backend=WakeWordBackend.ASR_PHRASE,
                    score=1.0,
                    transcript=preview,
                    audio=chunk,
                )
            await asyncio.sleep(0.1)
        raise BackendUnavailableError(
            f"wake phrase {self.phrase!r} not detected after {max_attempts} attempts"
        )
