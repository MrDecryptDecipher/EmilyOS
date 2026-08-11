"""Config loading tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from emily.config.loader import load_settings


def test_load_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    for key in ("APP_NAME", "EMILY_APP_NAME", "PRIMARY_PROVIDER", "ALLOW_TERMINAL"):
        monkeypatch.delenv(key, raising=False)
    settings = load_settings(env_file=tmp_path / "missing.env")
    assert settings.app_name == "Emily OS"
    assert settings.primary_provider == "nvidia"
    assert settings.nvidia_model == "z-ai/glm-5.2"
    assert settings.routesme_model == "DeepSeek-V4-Flash-0731"
    assert settings.allow_terminal is False


def test_load_legacy_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "\n".join(
            [
                "APP_NAME=LegacyEmily",
                "PRIMARY_PROVIDER=NVIDIA",
                "ALLOW_TERMINAL=true",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    settings = load_settings(env_file=env)
    assert settings.app_name == "LegacyEmily"
    assert settings.primary_provider == "nvidia"
    assert settings.allow_terminal is True
