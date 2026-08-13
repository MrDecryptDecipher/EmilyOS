"""IndicF5 reference preset tests."""

from __future__ import annotations

from pathlib import Path

from emily.voice.indicf5_assets import resolve_indicf5_ref


def test_resolve_indicf5_ref_prefers_hindi_marathi_preset(tmp_path: Path) -> None:
    ref_dir = tmp_path / "indicf5_ref"
    ref_dir.mkdir()
    (ref_dir / "MAR_F_HAPPY_00001.wav").write_bytes(b"wav")

    class _Settings:
        voice_directory = tmp_path

    path, text = resolve_indicf5_ref(_Settings(), language="hi")
    assert path == ref_dir / "MAR_F_HAPPY_00001.wav"
    assert "भावा" in text
