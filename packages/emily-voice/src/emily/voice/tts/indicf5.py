"""IndicF5 TTS adapter — HuggingFace AutoModel trust_remote_code."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import numpy as np

from emily.voice.errors import BackendUnavailableError, ModelUnavailableError, TTSError
from emily.voice.indicf5_assets import resolve_indicf5_ref
from emily.voice.speech.bangla_tts import prepare_bengali_for_tts
from emily.voice.speech.hinglish_tts import prepare_hindi_for_tts
from emily.voice.models import AudioChunk, SpeechPlan, TTSCapability
from emily.voice.settings_bridge import resolve_device
from emily.voice.tts.registry import TTS_CAPABILITIES

_torchaudio_patched = False


def _patch_torchaudio_load() -> None:
    """Use soundfile for WAV I/O — torchaudio 2.9+ defaults to torchcodec (needs FFmpeg on Windows)."""
    global _torchaudio_patched
    if _torchaudio_patched:
        return
    import torch
    import torchaudio
    import soundfile as sf

    def _soundfile_load(
        filepath: str | Path,
        frame_offset: int = 0,
        num_frames: int = -1,
        normalize: bool = True,
        channels_first: bool = True,
        **_: Any,
    ) -> tuple[Any, int]:
        data, sr = sf.read(str(filepath), dtype="float32", always_2d=True)
        if frame_offset:
            data = data[int(frame_offset) :]
        if num_frames != -1:
            data = data[: int(num_frames)]
        tensor = torch.from_numpy(data.T.copy() if channels_first else data.copy())
        if normalize and tensor.numel() and float(tensor.abs().max()) > 1.0:
            tensor = tensor / tensor.abs().max()
        return tensor, sr

    torchaudio.load = _soundfile_load  # type: ignore[method-assign, assignment]
    _torchaudio_patched = True


def _local_model_dir(settings: Any | None) -> Path | None:
    """Return local IndicF5 weights directory if present (for verify/offline checks)."""
    candidates: list[Path] = []
    if settings is not None:
        models_dir = getattr(settings, "voice_models_directory", None)
        if models_dir:
            candidates.append(Path(models_dir) / "indicf5")
    candidates.extend([Path("models/voice/indicf5"), Path("data/voice/models/indicf5")])
    for path in candidates:
        if path.is_dir() and (path / "config.json").is_file():
            return path.resolve()
    return None


class IndicF5TTS:
    """
    Lazy IndicF5 adapter (ai4bharat/IndicF5 on HuggingFace).

    Install:
      pip install -e "packages/emily-voice[indicf5]"
      pip install "git+https://github.com/ai4bharat/IndicF5.git"
      hf auth login
      emily voice models --name indicf5 --download
    """

    name = "indicf5"

    def __init__(
        self,
        *,
        ref_audio_path: str | Path | None = None,
        ref_text: str | None = None,
        model_id: str = "ai4bharat/IndicF5",
        sample_rate: int = 24000,
        settings: Any | None = None,
        device: str | None = None,
    ) -> None:
        self.settings = settings
        self.model_id = model_id
        self.sample_rate = sample_rate
        self.device = device or resolve_device(settings)
        self._ref_audio_override = Path(ref_audio_path) if ref_audio_path else None
        self._ref_text_override = ref_text
        self._model: Any | None = None

    @property
    def capabilities(self) -> TTSCapability:
        return TTS_CAPABILITIES["indicf5"]

    def _resolved_ref(self, language: str | None = None) -> tuple[Path | None, str]:
        return resolve_indicf5_ref(
            self.settings,
            language=language,
            ref_audio_path=self._ref_audio_override,
            ref_text=self._ref_text_override,
        )

    def available(self) -> bool:
        try:
            import transformers  # noqa: F401
            import f5_tts  # noqa: F401
        except Exception:
            return False
        audio, text = self._resolved_ref()
        if audio is None or not audio.is_file():
            return False
        return bool(text.strip())

    def _import_model_cls(self) -> Any:
        try:
            from transformers import AutoModel

            return AutoModel
        except Exception as exc:
            raise BackendUnavailableError(
                "IndicF5 requires transformers; pip install 'emily-voice[indicf5]'",
                backend=self.name,
                cause=exc,
            ) from exc

    def _torch_device(self) -> str:
        import torch

        # IndicF5 + Whisper + Kokoro exceeds ~4GB cards (e.g. Quadro P2000) and hangs.
        if self.device == "cuda" and torch.cuda.is_available():
            try:
                props = torch.cuda.get_device_properties(0)
                vram_gb = float(props.total_memory) / (1024**3)
                if vram_gb < 6.0:
                    return "cpu"
            except Exception:
                pass
            return "cuda"
        if self.device == "mps" and getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _ensure_vocos(self) -> None:
        """Prefetch Vocos so first IndicF5 synth does not stall on a silent download."""
        try:
            from huggingface_hub import snapshot_download

            snapshot_download(
                repo_id="charactr/vocos-mel-24khz",
                local_files_only=False,
            )
        except Exception:
            # Best-effort — IndicF5 may still pull Vocos itself.
            pass

    async def load(self, *, language: str = "hi", on_status: Any | None = None) -> None:
        if self._model is not None:
            return

        def status(msg: str) -> None:
            if on_status is not None:
                on_status(msg)

        device = self._torch_device()
        status(
            f"Loading IndicF5 on {device} "
            "(first run may take a few minutes; low-VRAM GPUs use CPU)..."
        )
        timeout_s = 300.0 if device == "cpu" else 180.0
        if self.settings is not None:
            raw = getattr(self.settings, "voice_indicf5_load_timeout_s", None)
            if raw is not None:
                try:
                    timeout_s = max(60.0, float(raw))
                except (TypeError, ValueError):
                    pass
        try:
            await asyncio.wait_for(asyncio.to_thread(self._load_sync, language), timeout=timeout_s)
        except asyncio.TimeoutError as exc:
            raise BackendUnavailableError(
                f"IndicF5 load timed out after {timeout_s:.0f}s. "
                "Run: emily voice models --name indicf5 --download "
                "and ensure Vocos is cached (charactr/vocos-mel-24khz).",
                backend=self.name,
                cause=exc,
            ) from exc
        status("IndicF5 ready.")

    def _load_sync(self, language: str = "hi") -> None:
        if self._model is not None:
            return
        audio, text = self._resolved_ref(language)
        if audio is None or not audio.is_file():
            raise ModelUnavailableError(
                "IndicF5 requires reference audio. Set EMILY_VOICE_INDICF5_REF_AUDIO or run:\n"
                "  emily voice models --name indicf5-ref --download",
                details={"ref_audio_path": str(audio) if audio else None},
            )
        if not text.strip():
            raise ModelUnavailableError(
                "IndicF5 requires EMILY_VOICE_INDICF5_REF_TEXT (transcript of reference audio)",
                details={"ref_audio_path": str(audio)},
            )
        try:
            import f5_tts  # noqa: F401
        except Exception as exc:
            raise BackendUnavailableError(
                'IndicF5 requires f5_tts; pip install "git+https://github.com/ai4bharat/IndicF5.git"',
                backend=self.name,
                cause=exc,
            ) from exc
        _patch_torchaudio_load()
        self._ensure_vocos()
        model_cls = self._import_model_cls()
        device = self._torch_device()
        # HuggingFace transformers rejects Windows absolute paths as repo ids; load via hub id
        # (uses HF cache after `emily voice models --name indicf5 --download`).
        try:
            self._model = model_cls.from_pretrained(
                self.model_id,
                trust_remote_code=True,
                low_cpu_mem_usage=False,
            )
            if device != "cpu":
                self._model = self._model.to(device)
            else:
                self._model = self._model.to("cpu")
            if hasattr(self._model, "eval"):
                self._model.eval()
        except Exception as exc:
            raise BackendUnavailableError(
                f"failed to load IndicF5 model {self.model_id}: {exc}\n"
                "Ensure hf auth login and gate access at huggingface.co/ai4bharat/IndicF5",
                backend=self.name,
                cause=exc,
            ) from exc

    async def unload(self) -> None:
        self._model = None

    def _synthesize_sync(
        self,
        text: str,
        audio_path: Path,
        ref_text: str,
        speed: float,
    ) -> np.ndarray:
        assert self._model is not None
        if hasattr(self._model, "config"):
            self._model.config.speed = speed
        raw = self._model(
            text,
            ref_audio_path=str(audio_path),
            ref_text=ref_text,
        )
        if hasattr(raw, "dtype") and getattr(raw, "dtype", None) == np.int16:
            return np.asarray(raw, dtype=np.float32).reshape(-1) / 32768.0
        return np.asarray(raw, dtype=np.float32).reshape(-1)

    async def synthesize(self, plan: SpeechPlan) -> AudioChunk:
        await self.load(language=(plan.language or "hi").split("-")[0].lower())
        assert self._model is not None
        lang = (plan.language or "hi").split("-")[0].lower()
        audio_path, ref_text = self._resolved_ref(lang)
        assert audio_path is not None
        text = prepare_hindi_for_tts(
            plan.text if not plan.segments else " ".join(s.text for s in plan.segments),
            language=lang,
        )
        text = prepare_bengali_for_tts(text, language=lang)
        # Soft generation speed (does not pitch-shift like playback stretch).
        speed = max(0.78, min(0.90, float(plan.pace or 0.88)))
        # Soften shouty punctuation that pushes IndicF5 into aggressive prosody.
        text = text.replace("!", ".").replace("！", ".")
        text = " ".join(text.split())
        # CPU synth on Pascal-class machines can exceed 2 minutes for long lines.
        synth_timeout = 240.0 if self._torch_device() == "cpu" else 120.0
        try:
            arr = await asyncio.wait_for(
                asyncio.to_thread(
                    self._synthesize_sync,
                    text,
                    audio_path,
                    ref_text,
                    speed,
                ),
                timeout=synth_timeout,
            )
            if arr.size == 0:
                raise TTSError("IndicF5 produced empty audio", details={"backend": self.name})
            peak = float(np.max(np.abs(arr))) if arr.size else 0.0
            if peak > 1e-6:
                arr = arr * min(0.88, 0.68 / peak)
            return AudioChunk(
                samples=arr.astype(np.float32).tolist(),
                sample_rate=self.sample_rate,
                channels=1,
                backend=self.name,
            )
        except asyncio.TimeoutError as exc:
            raise TTSError(
                f"IndicF5 synthesis timed out after {synth_timeout:.0f}s",
                cause=exc,
                details={"backend": self.name},
            ) from exc
        except (BackendUnavailableError, ModelUnavailableError, TTSError):
            raise
        except Exception as exc:
            raise TTSError(f"IndicF5 synthesis failed: {exc}", cause=exc) from exc
