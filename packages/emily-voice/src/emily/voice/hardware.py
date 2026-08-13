"""Hardware capability detection for TTS routing."""

from __future__ import annotations

import os
from functools import lru_cache

from emily.voice.models import HardwareInfo, HardwareProfile


def _ram_gb() -> float:
    try:
        import psutil  # type: ignore[import-untyped]

        return float(psutil.virtual_memory().total) / (1024**3)
    except Exception:
        pass
    # Fallback: Windows / POSIX page size heuristics via os
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")  # type: ignore[attr-defined]
        pages = os.sysconf("SC_PHYS_PAGES")  # type: ignore[attr-defined]
        return float(page_size * pages) / (1024**3)
    except (AttributeError, OSError, ValueError):
        return 8.0


def _cuda_info() -> tuple[bool, str | None, float | None]:
    try:
        import torch  # type: ignore[import-untyped]

        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram: float | None = None
            try:
                props = torch.cuda.get_device_properties(0)
                vram = float(props.total_memory) / (1024**3)
            except Exception:
                vram = None
            return True, str(name), vram
    except Exception:
        pass
    return False, None, None


def _mps_available() -> bool:
    try:
        import torch  # type: ignore[import-untyped]

        return bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
    except Exception:
        return False


def classify_profile(*, cpu_count: int, ram_gb: float, cuda: bool) -> HardwareProfile:
    if cuda and ram_gb >= 12 and cpu_count >= 8:
        return HardwareProfile.HIGH
    if ram_gb >= 8 and cpu_count >= 4:
        return HardwareProfile.MEDIUM
    return HardwareProfile.LOW


def resolve_whisper_compute_type(device: str) -> str:
    """Pick a ctranslate2 compute type that works on the target device."""
    if device != "cuda":
        return "int8"
    try:
        import torch  # type: ignore[import-untyped]

        if torch.cuda.is_available():
            major, _minor = torch.cuda.get_device_capability(0)
            # Pascal (sm_61) and older GPUs lack efficient float16 in ctranslate2.
            if major < 7:
                return "float32"
            return "float16"
    except Exception:
        pass
    return "float16"


def resolve_torch_device(prefer: str = "auto") -> str:
    """Return cuda|mps|cpu honoring an explicit prefer or auto-detect order."""
    pref = (prefer or "auto").strip().lower()
    if pref in {"cuda", "mps", "cpu"}:
        if pref == "cuda":
            cuda, _, _ = _cuda_info()
            return "cuda" if cuda else "cpu"
        if pref == "mps":
            return "mps" if _mps_available() else "cpu"
        return "cpu"
    # auto
    cuda, _, _ = _cuda_info()
    if cuda:
        return "cuda"
    if _mps_available():
        return "mps"
    return "cpu"


@lru_cache(maxsize=1)
def detect_hardware() -> HardwareInfo:
    cpu_count = os.cpu_count() or 1
    ram = _ram_gb()
    cuda, device, vram = _cuda_info()
    mps = _mps_available()
    profile = classify_profile(cpu_count=cpu_count, ram_gb=ram, cuda=cuda)
    return HardwareInfo(
        cpu_count=cpu_count,
        ram_gb=round(ram, 2),
        cuda_available=cuda,
        cuda_device_name=device,
        mps_available=mps,
        vram_gb=round(vram, 2) if vram is not None else None,
        onnx_hint=False,
        profile=profile,
    )


def clear_hardware_cache() -> None:
    detect_hardware.cache_clear()
