"""Hugging Face Hub compatibility (Windows symlink privileges)."""

from __future__ import annotations

import os
import sys


def ensure_hf_hub_windows_compat() -> None:
    """
    On Windows without Developer Mode, HF Hub cannot create cache symlinks (WinError 1314).

    Force copy-based caching before any huggingface_hub / faster_whisper import.
    """
    if sys.platform != "win32":
        return
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
