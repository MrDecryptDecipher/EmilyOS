"""faster-whisper ASR adapter."""

from __future__ import annotations

import asyncio
import io
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import numpy as np

from emily.voice.asr.language_pick import (
    pick_best_transcription,
    retry_language_order,
    should_retry_transcription,
)
from emily.voice.audio.processing import ensure_float32_mono, resample
from emily.voice.errors import ASRError, BackendUnavailableError
from emily.voice.hardware import resolve_whisper_compute_type
from emily.voice.hf_compat import ensure_hf_hub_windows_compat
from emily.voice.models import AudioChunk


class FasterWhisperASR:
    name = "faster-whisper"

    def __init__(
        self,
        *,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        settings: Any | None = None,
    ) -> None:
        self.settings = settings
        self.model_size = (
            str(getattr(settings, "voice_asr_model", model_size)) if settings is not None else model_size
        )
        self.device = device
        if device == "cuda" and compute_type == "int8":
            self.compute_type = resolve_whisper_compute_type(device)
        else:
            self.compute_type = compute_type
        self._model: Any | None = None
        self.last_detected_language: str | None = None
        self.last_language_probability: float | None = None
        self.last_transcript: str = ""
        self.last_retry_used: bool = False

    def available(self) -> bool:
        try:
            from faster_whisper import WhisperModel  # noqa: F401

            return True
        except Exception:
            return False

    async def load(self) -> None:
        if self._model is not None:
            return
        await asyncio.to_thread(self._load_sync)

    def _load_sync(self) -> None:
        if self._model is not None:
            return
        ensure_hf_hub_windows_compat()
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:
            raise BackendUnavailableError(
                "faster-whisper is not installed; pip install 'emily-voice[asr]'",
                backend=self.name,
                cause=exc,
            ) from exc
        download_root = self._download_root()
        compute_types: list[str] = [self.compute_type]
        if self.device == "cuda":
            for alt in ("float32", "int8_float16"):
                if alt not in compute_types:
                    compute_types.append(alt)
        last_exc: Exception | None = None
        for compute_type in compute_types:
            try:
                kwargs: dict[str, Any] = {
                    "device": self.device,
                    "compute_type": compute_type,
                }
                if download_root is not None:
                    kwargs["download_root"] = download_root
                self._model = WhisperModel(self.model_size, **kwargs)
                self.compute_type = compute_type
                return
            except ValueError as exc:
                if "compute type" in str(exc).lower():
                    last_exc = exc
                    continue
                raise
            except OSError as exc:
                if getattr(exc, "winerror", None) == 1314 or "1314" in str(exc):
                    raise BackendUnavailableError(
                        f"failed to load Whisper model {self.model_size}: Windows blocked HF cache "
                        "symlinks. Set HF_HUB_DISABLE_SYMLINKS=1 in .env, then run: "
                        "powershell -File scripts/fix-whisper-cache.ps1",
                        backend=self.name,
                        cause=exc,
                    ) from exc
                raise BackendUnavailableError(
                    f"failed to load Whisper model {self.model_size}: {exc}",
                    backend=self.name,
                    cause=exc,
                ) from exc
            except Exception as exc:
                raise BackendUnavailableError(
                    f"failed to load Whisper model {self.model_size}: {exc}",
                    backend=self.name,
                    cause=exc,
                ) from exc
        if last_exc is not None:
            raise BackendUnavailableError(
                f"failed to load Whisper model {self.model_size}: {last_exc}",
                backend=self.name,
                cause=last_exc,
            ) from last_exc

    def _download_root(self) -> str | None:
        if self.settings is None:
            return None
        models_dir = getattr(self.settings, "voice_models_directory", None)
        if not models_dir:
            return None
        root = Path(models_dir) / "hf-cache"
        root.mkdir(parents=True, exist_ok=True)
        return str(root)

    async def unload(self) -> None:
        self._model = None
        self.last_detected_language = None
        self.last_language_probability = None
        self.last_transcript = ""
        self.last_retry_used = False

    def _configured_language(self) -> str | None:
        raw = getattr(self.settings, "voice_asr_language", None) if self.settings is not None else None
        if not raw:
            return None
        base = str(raw).split("-")[0].lower().strip()
        if base in {"", "auto"}:
            return None
        return base

    def _auto_detect_enabled(self) -> bool:
        if self.settings is None:
            return True
        return bool(getattr(self.settings, "voice_language_auto_detect", True))

    def _to_pcm16_array(self, audio: AudioChunk) -> np.ndarray:
        samples = ensure_float32_mono(audio.samples, channels=audio.channels)
        if audio.sample_rate != 16000:
            samples = resample(samples, audio.sample_rate, 16000)
        return samples

    def _transcribe_pcm(
        self,
        pcm: np.ndarray,
        *,
        language: str | None,
        vad_filter: bool = True,
        initial_prompt: str | None = None,
        condition_on_previous_text: bool = True,
    ) -> tuple[str, str | None, float | None]:
        assert self._model is not None
        kwargs: dict[str, Any] = {
            "language": language,
            "vad_filter": vad_filter,
            "condition_on_previous_text": condition_on_previous_text,
        }
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt
        segments, info = self._model.transcribe(pcm, **kwargs)
        parts: list[str] = []
        for seg in segments:
            text = getattr(seg, "text", str(seg))
            if text:
                parts.append(str(text).strip())
        transcript = " ".join(parts).strip()
        detected = getattr(info, "language", None)
        probability = getattr(info, "language_probability", None)
        detected_lang = str(detected).split("-")[0].lower() if detected else None
        prob = float(probability) if probability is not None else None
        return transcript, detected_lang, prob

    async def _transcribe_pcm_async(
        self,
        pcm: np.ndarray,
        *,
        language: str | None,
        vad_filter: bool = True,
        initial_prompt: str | None = None,
        condition_on_previous_text: bool = True,
    ) -> tuple[str, str | None, float | None]:
        return await asyncio.to_thread(
            self._transcribe_pcm,
            pcm,
            language=language,
            vad_filter=vad_filter,
            initial_prompt=initial_prompt,
            condition_on_previous_text=condition_on_previous_text,
        )

    async def _transcribe_with_retry_async(
        self,
        pcm: np.ndarray,
        *,
        language: str | None = None,
        language_hint: str | None = None,
        on_status: Callable[[str], None] | None = None,
        multilingual: bool = False,
        vad_filter: bool = True,
        max_indic_retries: int = 10,
    ) -> tuple[str, str | None, float | None, bool]:
        return await asyncio.to_thread(
            self._transcribe_with_retry,
            pcm,
            language=language,
            language_hint=language_hint,
            on_status=on_status,
            multilingual=multilingual,
            vad_filter=vad_filter,
            max_indic_retries=max_indic_retries,
        )

    def _transcribe_with_retry(
        self,
        pcm: np.ndarray,
        *,
        language: str | None = None,
        language_hint: str | None = None,
        on_status: Callable[[str], None] | None = None,
        multilingual: bool = False,
        vad_filter: bool = True,
        max_indic_retries: int = 10,
    ) -> tuple[str, str | None, float | None, bool]:
        def status(msg: str) -> None:
            if on_status is not None:
                on_status(msg)

        fixed = language or self._configured_language()
        if fixed:
            text, det, prob = self._transcribe_pcm(pcm, language=fixed, vad_filter=vad_filter)
            return text, det, prob, False

        candidates: list[tuple[str, str | None, float | None]] = []
        if language_hint and language_hint not in {"en", "auto"}:
            for lang in retry_language_order(language_hint)[: min(3, max_indic_retries)]:
                whisper_lang = "hi" if lang == "or" else lang
                try:
                    alt_text, alt_det, alt_prob = self._transcribe_pcm(
                        pcm, language=whisper_lang, vad_filter=vad_filter
                    )
                except ValueError:
                    continue
                candidates.append((alt_text, alt_det, alt_prob))

        text, det, prob = self._transcribe_pcm(pcm, language=None, vad_filter=vad_filter)
        candidates.append((text, det, prob))

        if not self._auto_detect_enabled():
            best_text, best_det, best_prob = pick_best_transcription(
                candidates, language_hint=language_hint
            )
            return best_text, best_det, best_prob, len(candidates) > 1

        needs_retry = should_retry_transcription(text, det, prob)
        if multilingual and language_hint and language_hint not in {"en", "auto"}:
            needs_retry = True
        if needs_retry:
            if not multilingual:
                prob_label = f"{prob:.0%}" if prob is not None else "n/a"
                status(
                    f"ASR auto-detect uncertain ({det or '?'} @ {prob_label}); "
                    "retrying with Indic language models..."
                )
            else:
                status(f"Transcribing question ({language_hint or 'indic'})...")
            tried = 0
            for lang in retry_language_order(language_hint):
                if tried >= max_indic_retries:
                    break
                whisper_lang = "hi" if lang == "or" else lang
                try:
                    alt_text, alt_det, alt_prob = self._transcribe_pcm(
                        pcm, language=whisper_lang, vad_filter=vad_filter
                    )
                except ValueError:
                    continue
                candidates.append((alt_text, alt_det, alt_prob))
                tried += 1
            best_text, best_det, best_prob = pick_best_transcription(
                candidates, language_hint=language_hint
            )
            if best_text != text:
                picked_prob = f"{best_prob:.0%}" if best_prob is not None else "n/a"
                status(f"ASR picked {best_det or '?'} transcript ({picked_prob} confidence).")
            return best_text, best_det, best_prob, True

        best_text, best_det, best_prob = pick_best_transcription(
            candidates, language_hint=language_hint
        )
        return best_text, best_det, best_prob, len(candidates) > 1

    async def transcribe(
        self,
        audio: AudioChunk,
        *,
        language: str | None = None,
        language_hint: str | None = None,
        on_status: Callable[[str], None] | None = None,
        multilingual: bool = False,
        vad_filter: bool = True,
        max_indic_retries: int = 10,
    ) -> str:
        parts: list[str] = []
        async for segment in self.transcribe_stream(
            audio,
            language=language,
            language_hint=language_hint,
            on_status=on_status,
            multilingual=multilingual,
            vad_filter=vad_filter,
            max_indic_retries=max_indic_retries,
        ):
            if segment.strip():
                parts.append(segment.strip())
        return " ".join(parts).strip()

    async def transcribe_wake(
        self,
        audio: AudioChunk,
        *,
        wake_phrase: str = "Hey Emily",
        on_status: Callable[[str], None] | None = None,
    ) -> str:
        """
        Wake-word ASR: no VAD stripping, prompt-biased, filters common hallucinations.

        Whisper's VAD often deletes short "Hey Emily" clips on Windows; disabling it and
        using an initial prompt greatly improves hit rate.
        """
        from emily.voice.asr.language_pick import looks_like_wake_hallucination

        await self.load()
        assert self._model is not None
        pcm = self._to_pcm16_array(audio)
        if pcm.size == 0:
            self.last_transcript = ""
            return ""
        text, detected, prob = await self._transcribe_pcm_async(
            pcm,
            language="en",
            vad_filter=False,
            initial_prompt=wake_phrase,
            condition_on_previous_text=False,
        )
        if looks_like_wake_hallucination(text, wake_phrase=wake_phrase):
            if on_status is not None:
                on_status("Filtered ASR hallucination (no wake phrase detected in audio).")
            text = ""
        self.last_detected_language = detected
        self.last_language_probability = prob
        self.last_transcript = text
        self.last_retry_used = False
        return text

    async def transcribe_wake_followup(
        self,
        audio: AudioChunk,
        *,
        language_hint: str | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> str:
        """Fast wake follow-up ASR: Hindi-first for Hinglish, capped Indic retries."""
        from emily.voice.asr.language_pick import detect_language_hint_from_text

        hint = language_hint or detect_language_hint_from_text("") or "hi"
        # Hinglish wake follow-ups: force Hindi path — shopping ta/te/bn often hallucinates.
        if hint in {"hi", "mr", None, ""}:
            return await self.transcribe(
                audio,
                language="hi",
                language_hint="hi",
                on_status=on_status,
                multilingual=False,
                vad_filter=False,
                max_indic_retries=1,
            )
        return await self.transcribe(
            audio,
            language_hint=hint,
            on_status=on_status,
            multilingual=True,
            vad_filter=False,
            max_indic_retries=2,
        )

    async def transcribe_followup(
        self,
        audio: AudioChunk,
        *,
        wake_phrase: str = "Hey Emily",
        language_hint: str | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> str:
        """Re-transcribe wake audio when English wake path may have mis-heard Indic speech."""
        return await self.transcribe_wake_followup(
            audio,
            language_hint=language_hint,
            on_status=on_status,
        )

    async def transcribe_stream(
        self,
        audio: AudioChunk,
        *,
        language: str | None = None,
        language_hint: str | None = None,
        on_status: Callable[[str], None] | None = None,
        multilingual: bool = False,
        vad_filter: bool = True,
        max_indic_retries: int = 4,
    ) -> AsyncIterator[str]:
        await self.load()
        assert self._model is not None
        pcm = self._to_pcm16_array(audio)
        if pcm.size == 0:
            self.last_detected_language = None
            self.last_language_probability = None
            self.last_transcript = ""
            self.last_retry_used = False
            return
        lang = language.split("-")[0] if language else None
        hint = language_hint.split("-")[0] if language_hint else None
        try:
            text, detected, prob, retried = await self._transcribe_with_retry_async(
                pcm,
                language=lang,
                language_hint=hint,
                on_status=on_status,
                multilingual=multilingual,
                vad_filter=vad_filter,
                max_indic_retries=max_indic_retries,
            )
            self.last_detected_language = detected
            self.last_language_probability = prob
            self.last_transcript = text
            self.last_retry_used = retried
            if text:
                yield text
        except Exception as exc:
            if isinstance(audio.samples, bytes):
                try:
                    import soundfile as sf

                    data, sr = sf.read(io.BytesIO(audio.samples), dtype="float32")
                    chunk = AudioChunk(samples=np.asarray(data).tolist(), sample_rate=int(sr), channels=1)
                    async for seg in self.transcribe_stream(
                        chunk,
                        language=language,
                        language_hint=language_hint,
                        on_status=on_status,
                    ):
                        yield seg
                    return
                except Exception as inner:
                    raise ASRError(f"ASR failed: {exc}", cause=inner) from inner
            raise ASRError(f"ASR failed: {exc}", cause=exc) from exc
