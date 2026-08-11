"""Settings loader helpers."""

from __future__ import annotations

from pathlib import Path

from emily.config.settings import EmilySettings
from emily.core.errors import ConfigError


def load_settings(env_file: str | Path | None = None) -> EmilySettings:
    """Load settings, optionally from an explicit env file path."""

    try:
        if env_file is None:
            return EmilySettings()
        return EmilySettings(_env_file=str(env_file))
    except Exception as exc:
        raise ConfigError("failed to load Emily settings", details={"error": str(exc)}) from exc
