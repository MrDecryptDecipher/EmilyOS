"""Shared voice test helpers — real backends only."""

from __future__ import annotations

import pytest

from emily.voice.tts.kokoro import KokoroTTS


def kokoro_available() -> bool:
    return KokoroTTS().available()


@pytest.fixture
def require_kokoro() -> None:
    if not kokoro_available():
        pytest.skip("kokoro is not installed; pip install 'emily-voice[kokoro]'")
