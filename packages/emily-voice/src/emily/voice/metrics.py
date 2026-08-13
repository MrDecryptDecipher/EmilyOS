"""Voice metrics — never log raw audio; redact transcripts unless debug."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from emily.voice.models import VoiceMetricsSnapshot


def redact_transcript(text: str, *, debug: bool = False, max_chars: int = 48) -> str:
    if debug:
        return text
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return f"[redacted len={len(cleaned)}]"
    return f"[redacted len={len(cleaned)} preview={cleaned[:12]}…]"


class VoiceMetrics:
    """Collects VAD / ASR / LLM / TTS / TTFA / RTF latencies."""

    def __init__(self, *, logger: Any | None = None, debug: bool = False) -> None:
        self.logger = logger
        self.debug = debug
        self.vad_latency_ms = 0.0
        self.asr_latency_ms = 0.0
        self.llm_latency_ms = 0.0
        self.tts_latency_ms = 0.0
        self.ttfa_ms = 0.0
        self.asr_rtf = 0.0
        self.tts_rtf = 0.0
        self.memory_mb: float | None = None
        self.end_to_end_ms = 0.0
        self.turns = 0
        self.barge_ins = 0
        self.errors = 0
        self.last_backend: str | None = None
        self._turn_start: float | None = None
        self._first_audio: bool = False

    def begin_turn(self) -> None:
        self._turn_start = time.perf_counter()
        self._first_audio = False

    def record_vad(self, latency_ms: float) -> None:
        self.vad_latency_ms = float(latency_ms)
        self._hist("voice.vad_ms", latency_ms)

    def record_asr(self, latency_ms: float) -> None:
        self.asr_latency_ms = float(latency_ms)
        self._hist("voice.asr_ms", latency_ms)

    def record_llm(self, latency_ms: float) -> None:
        self.llm_latency_ms = float(latency_ms)
        self._hist("voice.llm_ms", latency_ms)

    def record_tts(self, latency_ms: float, *, backend: str | None = None) -> None:
        self.tts_latency_ms = float(latency_ms)
        if backend:
            self.last_backend = backend
        self._hist("voice.tts_ms", latency_ms, tags={"backend": backend or "unknown"})

    def record_asr_rtf(self, generation_time_s: float, audio_duration_s: float) -> None:
        if audio_duration_s <= 0:
            self.asr_rtf = 0.0
        else:
            self.asr_rtf = float(generation_time_s) / float(audio_duration_s)
        self._hist("voice.asr_rtf", self.asr_rtf)

    def record_tts_rtf(self, generation_time_s: float, audio_duration_s: float) -> None:
        if audio_duration_s <= 0:
            self.tts_rtf = 0.0
        else:
            self.tts_rtf = float(generation_time_s) / float(audio_duration_s)
        self._hist("voice.tts_rtf", self.tts_rtf)

    def record_memory(self, memory_mb: float | None = None) -> None:
        if memory_mb is not None:
            self.memory_mb = float(memory_mb)
        else:
            try:
                import psutil  # type: ignore[import-untyped]

                self.memory_mb = float(psutil.Process().memory_info().rss) / (1024**2)
            except Exception:
                self.memory_mb = None
        if self.memory_mb is not None:
            self._hist("voice.memory_mb", self.memory_mb)

    def record_e2e(self, latency_ms: float | None = None) -> None:
        if latency_ms is not None:
            self.end_to_end_ms = float(latency_ms)
        elif self._turn_start is not None:
            self.end_to_end_ms = (time.perf_counter() - self._turn_start) * 1000.0
        self._hist("voice.e2e_ms", self.end_to_end_ms)

    def mark_first_audio(self) -> None:
        if self._first_audio or self._turn_start is None:
            return
        self._first_audio = True
        self.ttfa_ms = (time.perf_counter() - self._turn_start) * 1000.0
        self._hist("voice.ttfa_ms", self.ttfa_ms)

    def record_turn(self) -> None:
        self.turns += 1
        self._counter("voice.turns")

    def record_barge_in(self) -> None:
        self.barge_ins += 1
        self._counter("voice.barge_ins")

    def record_error(self, message: str, *, tags: Mapping[str, str] | None = None) -> None:
        self.errors += 1
        self._counter("voice.errors", tags=tags)
        self.log_event("voice.error", message=message, **dict(tags or {}))

    def snapshot(self) -> VoiceMetricsSnapshot:
        return VoiceMetricsSnapshot(
            vad_latency_ms=self.vad_latency_ms,
            asr_latency_ms=self.asr_latency_ms,
            llm_latency_ms=self.llm_latency_ms,
            tts_latency_ms=self.tts_latency_ms,
            ttfa_ms=self.ttfa_ms,
            asr_rtf=self.asr_rtf,
            tts_rtf=self.tts_rtf,
            memory_mb=self.memory_mb,
            end_to_end_ms=self.end_to_end_ms,
            turns=self.turns,
            barge_ins=self.barge_ins,
            errors=self.errors,
            last_backend=self.last_backend,
        )

    def log_event(self, event: str, *, transcript: str | None = None, **fields: Any) -> None:
        """Structured log helper — never accepts or logs raw audio samples."""
        if self.logger is None:
            return
        payload = {k: v for k, v in fields.items() if k not in {"audio", "samples", "pcm", "wav"}}
        if transcript is not None:
            payload["transcript"] = redact_transcript(transcript, debug=self.debug)
        try:
            self.logger.info(event, **payload)
        except Exception:
            pass

    def _hist(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        metrics = getattr(self.logger, "metrics", None) if self.logger is not None else None
        if metrics is None:
            return
        try:
            metrics.histogram(name, float(value), tags=dict(tags or {}))
        except Exception:
            pass

    def _counter(self, name: str, *, tags: Mapping[str, str] | None = None) -> None:
        metrics = getattr(self.logger, "metrics", None) if self.logger is not None else None
        if metrics is None:
            return
        try:
            metrics.counter(name, 1.0, tags=dict(tags or {}))
        except Exception:
            pass
