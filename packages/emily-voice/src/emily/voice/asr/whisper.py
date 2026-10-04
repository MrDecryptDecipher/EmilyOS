"""faster-whisper ASR adapter."""

from __future__ import annotations

import asyncio
import io
import re
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from emily.voice.asr.bangla_asr import BanglaASR

from emily.voice.asr.language_pick import should_retry_transcription
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
        bangla: BanglaASR | None = None,
    ) -> None:
        self.settings = settings
        self._bangla = bangla
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

    def _bangla_ready(self) -> bool:
        return self._bangla is not None and self._bangla.available()

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
        if language == "bn" and self._bangla_ready():
            assert self._bangla is not None
            if self._bangla._model is None:
                self._bangla._load_sync()
            text, det, prob = self._bangla.transcribe_pcm(pcm)
            return text, det, prob

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

    def _transcribe_universal(
        self,
        pcm: np.ndarray,
        *,
        vad_filter: bool = True,
        on_status: Callable[[str], None] | None = None,
    ) -> tuple[str, str | None, float | None, bool]:
        """
        Universal ASR: Whisper auto-detect any language, then refine once.

        Specialty models (e.g. BanglaASR) run only when auto-detect matches their
        language — never in competition with other languages.
        """
        def status(msg: str) -> None:
            if on_status is not None:
                on_status(msg)

        text, det, prob = self._transcribe_pcm(pcm, language=None, vad_filter=vad_filter)
        lang = (det or "").split("-")[0].lower()
        retried = False

        # BanglaASR whenever Whisper says Bengali — do not remap bn→hi.
        # False English→bn flips are corrected later in resolve_wake_question.
        if lang == "bn" and self._bangla_ready():
            status("Transcribing (BanglaASR)...")
            assert self._bangla is not None
            if self._bangla._model is None:
                self._bangla._load_sync()
            text, det, prob = self._bangla.transcribe_pcm(pcm)
            return text, det, prob, True

        # Roman Bangla often auto-detects as hi/en — route to BanglaASR on strong hints.
        from emily.voice.bangla_hints import looks_like_roman_bangla

        if (
            self._bangla_ready()
            and looks_like_roman_bangla(text or "")
            and lang in {"", "en", "hi", "auto", "ur"}
        ):
            status("Transcribing (BanglaASR — roman Bangla cues)...")
            assert self._bangla is not None
            if self._bangla._model is None:
                self._bangla._load_sync()
            text, det, prob = self._bangla.transcribe_pcm(pcm)
            return text, det, prob, True

        if lang and lang not in {"", "en", "auto"}:
            uncertain = should_retry_transcription(text, det, prob) or (
                prob is not None and prob < 0.55
            )
            refine = uncertain or prob is None or prob >= 0.45
            refine_lang = lang
            # Hinglish is often mislabeled as Urdu — refine as Hindi, never as Urdu.
            if refine and lang == "ur" and (prob is None or prob < 0.70):
                refine_lang = "hi"
            if refine:
                status(f"Transcribing ({refine_lang})...")
                text, det, prob = self._transcribe_pcm(
                    pcm, language=refine_lang, vad_filter=vad_filter
                )
                retried = True

        return text, det, prob, retried

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
        if fixed == "bn" and self._bangla_ready():
            assert self._bangla is not None
            if self._bangla._model is None:
                self._bangla._load_sync()
            text, det, prob = self._bangla.transcribe_pcm(pcm)
            return text, det, prob, False

        if fixed:
            text, det, prob = self._transcribe_pcm(pcm, language=fixed, vad_filter=vad_filter)
            return text, det, prob, False

        text, det, prob, retried = self._transcribe_universal(
            pcm, vad_filter=vad_filter, on_status=on_status
        )
        return text, det, prob, retried

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

    async def transcribe_wake_question(
        self,
        audio: AudioChunk,
        *,
        on_status: Callable[[str], None] | None = None,
        english_wake_hint: str | None = None,
    ) -> str:
        """Wake follow-up: universal auto-detect (any language)."""
        await self.load()
        pcm = self._to_pcm16_array(audio)
        if pcm.size == 0:
            self.last_transcript = ""
            return ""

        if on_status is not None:
            on_status("Transcribing your question (auto-detect)...")

        text, det, prob, retried = await asyncio.to_thread(
            self._transcribe_universal,
            pcm,
            vad_filter=False,
            on_status=on_status,
        )

        # Bengali spoken after "Hey Emily" is often heard as English "how are you?"
        # and then mis-refined as weak Hindi → Devanagari garbage. Retry BanglaASR.
        text, det, prob, retried = await asyncio.to_thread(
            self._maybe_bangla_wake_retry,
            pcm,
            text,
            det,
            prob,
            retried,
            english_wake_hint,
            on_status,
        )

        self.last_detected_language = det
        self.last_language_probability = prob
        self.last_transcript = text or ""
        self.last_retry_used = retried
        if on_status is not None and det:
            prob_label = f"{prob:.0%}" if prob is not None else "n/a"
            on_status(f"Detected language: {det} ({prob_label})")
        return text or ""

    def _maybe_bangla_wake_retry(
        self,
        pcm: np.ndarray,
        text: str | None,
        det: str | None,
        prob: float | None,
        retried: bool,
        english_wake_hint: str | None,
        on_status: Callable[[str], None] | None,
    ) -> tuple[str | None, str | None, float | None, bool]:
        from emily.voice.asr.language_pick import looks_like_garbage_indic_transcript
        from emily.voice.bangla_hints import (
            looks_like_bengali_misheard_as_english,
            looks_like_roman_bangla,
            wake_english_likely_indic_speech,
        )
        from emily.voice.language import has_bengali

        def status(msg: str) -> None:
            if on_status is not None:
                on_status(msg)

        hint = (english_wake_hint or "").strip()
        lang = (det or "").split("-")[0].lower()
        current = (text or "").strip()
        hint_norm = hint.lower().strip(" ,.!?")
        current_norm = current.lower().strip(" ,.!?")
        indic_wake = wake_english_likely_indic_speech(hint)

        if has_bengali(current) and not looks_like_garbage_indic_transcript(current):
            return text, det, prob, retried
        if not self._bangla_ready():
            return text, det, prob, retried

        # Wake echoed back as the "question" (Whisper re-heard English translation).
        wake_echo = bool(hint_norm and current_norm and hint_norm == current_norm)
        want_bangla = (
            looks_like_roman_bangla(hint)
            or looks_like_bengali_misheard_as_english(hint)
            or looks_like_garbage_indic_transcript(current)
            or wake_echo
            or indic_wake
        )
        if not want_bangla:
            return text, det, prob, retried
        # Confident clean Hindi — keep unless wake text screams Indic mistranslation.
        if (
            lang == "hi"
            and prob is not None
            and prob >= 0.75
            and current
            and not looks_like_garbage_indic_transcript(current)
            and not looks_like_roman_bangla(hint)
        ):
            return text, det, prob, retried

        status("Transcribing (BanglaASR — checking Bengali)...")
        assert self._bangla is not None
        if self._bangla._model is None:
            self._bangla._load_sync()
        res = self._bangla.transcribe_pcm(pcm)
        if isinstance(res, (tuple, list)) and len(res) >= 3:
            bn_text, bn_det, bn_prob = res[0], res[1], res[2]
        else:
            bn_text, bn_det, bn_prob = "", "bn", 0.0
        bn_text = (bn_text or "").strip()
        if has_bengali(bn_text) and not looks_like_garbage_indic_transcript(bn_text):
            return bn_text, bn_det or "bn", bn_prob, True
        if looks_like_garbage_indic_transcript(current) and not bn_text:
            return text, det, prob, retried
        return text, det, prob, retried

    async def transcribe_wake_followup(
        self,
        audio: AudioChunk,
        *,
        language_hint: str | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> str:
        """Wake follow-up — delegates to language-agnostic auto-detect."""
        _ = language_hint
        return await self.transcribe_wake_question(audio, on_status=on_status)

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
