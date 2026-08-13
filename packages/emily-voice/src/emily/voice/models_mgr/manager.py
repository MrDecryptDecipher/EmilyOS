"""Model manager — no silent multi-GB downloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from emily.voice.errors import ModelUnavailableError
from emily.voice.models import ModelStatus
from emily.voice.tts.base import TTSEngine

# Catalog of known voice models with install hints (not auto-downloaded).
_MODEL_CATALOG: dict[str, dict[str, Any]] = {
    "kokoro": {
        "size_hint": "~300MB",
        "path": "data/voice/models/kokoro",
        "instructions": (
            "pip install 'emily-voice[kokoro]'\n"
            "Kokoro pulls voices on first use via its own pipeline — "
            "prefer explicit emily voice models download kokoro --allow-download"
        ),
    },
    "indicf5": {
        "size_hint": "~1-3GB",
        "path": "data/voice/models/indicf5",
        "repo_id": "ai4bharat/IndicF5",
        "instructions": (
            "pip install 'emily-voice[indicf5]'\n"
            "pip install \"git+https://github.com/ai4bharat/IndicF5.git\"\n"
            "hf auth login  # accept gated model license at huggingface.co/ai4bharat/IndicF5\n"
            "emily voice models --name indicf5 --download\n"
            "emily voice models --name indicf5-ref --download\n"
            "Set EMILY_VOICE_INDICF5_REF_AUDIO / EMILY_VOICE_INDICF5_REF_TEXT or use bundled ref."
        ),
    },
    "indicf5-ref": {
        "size_hint": "~1MB",
        "path": "data/voice/indicf5_ref",
        "instructions": (
            "emily voice models --name indicf5-ref --download\n"
            "Downloads default PAN_F_HAPPY_00001.wav + ref transcript from AI4Bharat/IndicF5."
        ),
    },
    "chatterbox": {
        "size_hint": "~1-2GB",
        "path": "data/voice/models/chatterbox",
        "instructions": (
            "pip install 'emily-voice[chatterbox]'\n"
            "Models load via ChatterboxMultilingualTTS.from_pretrained on first use."
        ),
    },
    "faster-whisper-base": {
        "size_hint": "~150MB",
        "path": "data/voice/models/faster-whisper-base",
        "repo_id": "Systran/faster-whisper-base",
        "instructions": (
            "pip install 'emily-voice[asr]'\n"
            "Windows: set HF_HUB_DISABLE_SYMLINKS=1 or run scripts/fix-whisper-cache.ps1\n"
            "emily voice models download faster-whisper-base --allow-download"
        ),
    },
    "faster-whisper-small": {
        "size_hint": "~500MB",
        "path": "data/voice/models/faster-whisper-small",
        "repo_id": "Systran/faster-whisper-small",
        "instructions": (
            "Set EMILY_VOICE_ASR_MODEL=small for better Hindi/Hinglish.\n"
            "Windows: HF_HUB_DISABLE_SYMLINKS=1 + scripts/fix-whisper-cache.ps1 if WinError 1314."
        ),
    },
    "silero-vad": {
        "size_hint": "~2MB",
        "path": "data/voice/models/silero-vad",
        "instructions": (
            "Silero VAD loads via torch.hub on first VAD use only.\n"
            "Set EMILY_VOICE_PREFER_ENERGY_VAD=true to avoid hub download and use EnergyVAD."
        ),
    },
}


class ModelManager:
    """Track voice model install/load status; download only when explicitly allowed."""

    def __init__(
        self,
        *,
        root: Path | str | None = None,
        settings: Any | None = None,
        engines: dict[str, TTSEngine] | None = None,
    ) -> None:
        if root is not None:
            self.root = Path(root)
        elif settings is not None and getattr(settings, "voice_models_directory", None):
            self.root = Path(settings.voice_models_directory)
        else:
            self.root = Path("data/voice/models")
        self.settings = settings
        self._loaded: set[str] = set()
        self._engines: dict[str, TTSEngine] = dict(engines or {})

    def bind_engines(self, engines: dict[str, TTSEngine]) -> None:
        self._engines = dict(engines)

    def status(self, name: str | None = None) -> list[ModelStatus]:
        names = [name] if name else list(_MODEL_CATALOG)
        result: list[ModelStatus] = []
        for key in names:
            meta = _MODEL_CATALOG.get(key)
            if meta is None:
                result.append(
                    ModelStatus(
                        name=key or "unknown",
                        installed=False,
                        download_instructions=f"unknown model {key!r}",
                    )
                )
                continue
            path = self.root / Path(meta["path"]).name
            catalog_path = Path(meta["path"])
            installed = path.exists() or catalog_path.exists() or self._package_hint_installed(key)
            result.append(
                ModelStatus(
                    name=key,
                    installed=installed,
                    loaded=key in self._loaded,
                    path=str(path),
                    size_hint=meta.get("size_hint"),
                    download_instructions=str(meta.get("instructions", "")),
                    details={"repo_id": meta.get("repo_id")},
                )
            )
        return result

    def check(self, name: str) -> ModelStatus:
        items = self.status(name)
        return items[0]

    def verify(self, name: str) -> ModelStatus:
        """Check files/imports for a model and return status with verify details."""
        status = self.check(name)
        details = dict(status.details)
        details["verified"] = False
        details["checks"] = []

        meta = _MODEL_CATALOG.get(name)
        path = Path(status.path) if status.path else None
        if path is not None and path.exists():
            details["checks"].append("path_exists")
        if self._package_hint_installed(name):
            details["checks"].append("import_ok")
        if name == "indicf5":
            ref = getattr(self.settings, "voice_indicf5_ref_audio", None) if self.settings else None
            if ref and Path(str(ref)).is_file():
                details["checks"].append("ref_audio_ok")
            else:
                from emily.voice.indicf5_assets import default_ref_dir, DEFAULT_REF_FILENAME

                bundled = default_ref_dir(self.settings) / DEFAULT_REF_FILENAME
                if bundled.is_file():
                    details["checks"].append("bundled_ref_audio_ok")
            if self.settings and str(getattr(self.settings, "voice_indicf5_ref_text", "") or "").strip():
                details["checks"].append("ref_text_ok")
        if name == "indicf5-ref":
            from emily.voice.indicf5_assets import default_ref_dir, DEFAULT_REF_FILENAME

            if (default_ref_dir(self.settings) / DEFAULT_REF_FILENAME).is_file():
                details["checks"].append("ref_audio_ok")
                details["verified"] = True
        if name == "silero-vad":
            details["checks"].append("lazy_hub_on_first_use")
            if self.settings is not None and getattr(self.settings, "voice_prefer_energy_vad", False):
                details["checks"].append("prefer_energy_vad")

        ok = bool(details["checks"]) and (
            "import_ok" in details["checks"] or "path_exists" in details["checks"] or name == "silero-vad"
        )
        details["verified"] = ok
        if meta is None:
            details["verified"] = False
        return status.model_copy(update={"details": details, "installed": status.installed or ok})

    def download_instructions(self, name: str) -> str:
        meta = _MODEL_CATALOG.get(name)
        if meta is None:
            return f"Unknown model {name!r}. Known: {', '.join(_MODEL_CATALOG)}"
        path = self.root / Path(meta["path"]).name
        return (
            f"Model: {name}\n"
            f"Expected path: {path}\n"
            f"Size: {meta.get('size_hint', 'unknown')}\n"
            f"{meta.get('instructions', '')}\n"
            "NOTE: Emily never auto-downloads multi-GB models on import/start."
        )

    def download(self, name: str, *, allow_download: bool = False) -> ModelStatus:
        """
        Download ONLY when allow_download=True (explicit CLI/user request).

        Uses huggingface_hub.snapshot_download when a repo_id is known.
        """
        if not allow_download:
            raise ModelUnavailableError(
                f"refusing to download {name!r} without allow_download=True",
                details={"instructions": self.download_instructions(name)},
            )
        meta = _MODEL_CATALOG.get(name)
        if meta is None:
            raise ModelUnavailableError(f"unknown model {name!r}")
        if name == "indicf5-ref":
            from emily.voice.indicf5_assets import default_ref_dir, download_default_ref

            target = default_ref_dir(self.settings)
            download_default_ref(target)
            return self.check("indicf5-ref")
        repo_id = meta.get("repo_id")
        target = self.root / Path(meta["path"]).name
        target.mkdir(parents=True, exist_ok=True)
        if not repo_id:
            # Package-managed models: print instructions only
            return ModelStatus(
                name=name,
                installed=self._package_hint_installed(name),
                path=str(target),
                size_hint=meta.get("size_hint"),
                download_instructions=self.download_instructions(name),
                details={"action": "package_install_required"},
            )
        try:
            from huggingface_hub import snapshot_download
        except Exception as exc:
            raise ModelUnavailableError(
                "huggingface_hub is required for explicit downloads",
                details={"cause": str(exc), "instructions": self.download_instructions(name)},
            ) from exc
        snapshot_download(repo_id=repo_id, local_dir=str(target))
        return self.check(name)

    async def load_engine(self, name: str) -> None:
        engine = self._engines.get(name)
        if engine is None:
            raise ModelUnavailableError(f"no TTS engine registered for {name!r}")
        load = getattr(engine, "load", None)
        if load is not None:
            await load()
        self.mark_loaded(name)

    async def unload_engine(self, name: str) -> None:
        engine = self._engines.get(name)
        if engine is not None:
            unload = getattr(engine, "unload", None)
            if unload is not None:
                await unload()
        self.mark_unloaded(name)

    def mark_loaded(self, name: str) -> None:
        self._loaded.add(name)

    def mark_unloaded(self, name: str) -> None:
        self._loaded.discard(name)

    def unload(self, name: str) -> None:
        self.mark_unloaded(name)

    @staticmethod
    def _package_hint_installed(name: str) -> bool:
        try:
            if name == "kokoro":
                from kokoro import KPipeline  # noqa: F401

                return True
            if name == "chatterbox":
                try:
                    from chatterbox.mtl_tts import ChatterboxMultilingualTTS  # noqa: F401

                    return True
                except Exception:
                    import chatterbox  # noqa: F401

                    return True
            if name == "indicf5":
                try:
                    import f5_tts  # noqa: F401
                    import transformers  # noqa: F401

                    return True
                except Exception:
                    return False
            if name == "indicf5-ref":
                from emily.voice.indicf5_assets import default_ref_dir, LANGUAGE_REF_PRESETS

                ref_dir = default_ref_dir(self.settings)
                hi_file = LANGUAGE_REF_PRESETS["hi"][0]
                return (ref_dir / hi_file).is_file() or (ref_dir / "PAN_F_HAPPY_00001.wav").is_file()
            if name.startswith("faster-whisper"):
                from faster_whisper import WhisperModel  # noqa: F401

                return True
            if name == "silero-vad":
                import torch  # noqa: F401

                return True
        except Exception:
            return False
        return False
