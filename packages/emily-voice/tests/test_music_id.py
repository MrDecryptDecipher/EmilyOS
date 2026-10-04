"""Tests for Emily OS music identification engine (music_id.py)."""

from __future__ import annotations

import io
import struct
import wave
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from emily.voice.music_id import (
    MusicIdentifier,
    MusicIdentifyResult,
    SongMatch,
    _parse_audd_response,
    _pcm_to_wav_bytes,
    identify_ambient_audio,
)


# ---------------------------------------------------------------------------
# WAV encoding helpers
# ---------------------------------------------------------------------------


def test_pcm_to_wav_bytes_encodes_mono() -> None:
    """Should produce a valid WAV header with correct channel/rate/frame params."""
    samples = np.zeros(44100, dtype=np.float32)
    wav = _pcm_to_wav_bytes(samples, sample_rate=44100, channels=1)

    buf = io.BytesIO(wav)
    with wave.open(buf, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 44100
        assert wf.getsampwidth() == 2  # int16


def test_pcm_to_wav_bytes_clips_amplitude() -> None:
    """Samples outside [-1, 1] should clip gracefully without OverflowError."""
    samples = np.array([2.0, -3.0, 0.5, -0.5], dtype=np.float32)
    wav = _pcm_to_wav_bytes(samples, sample_rate=44100, channels=1)
    assert len(wav) > 44  # WAV header is at least 44 bytes


# ---------------------------------------------------------------------------
# AudD response parsing
# ---------------------------------------------------------------------------


def test_parse_audd_response_success() -> None:
    raw = {
        "status": "success",
        "result": {
            "title": "Bohemian Rhapsody",
            "artist": "Queen",
            "album": "A Night at the Opera",
            "release_date": "1975-11-21",
            "label": "EMI",
            "spotify": {
                "id": "abc123",
                "album": {"images": [{"url": "https://example.com/cover.jpg"}]},
            },
            "apple_music": {"url": "https://music.apple.com/abc"},
        },
    }
    match = _parse_audd_response(raw)
    assert match is not None
    assert match.title == "Bohemian Rhapsody"
    assert match.artist == "Queen"
    assert match.album == "A Night at the Opera"
    assert match.spotify_id == "abc123"
    assert match.cover_art_url == "https://example.com/cover.jpg"
    assert match.apple_music_url == "https://music.apple.com/abc"
    assert match.confidence > 0.8


def test_parse_audd_response_no_match() -> None:
    raw = {"status": "success", "result": None}
    assert _parse_audd_response(raw) is None


def test_parse_audd_response_error_status() -> None:
    raw = {"status": "error", "error": {"error_message": "no token"}}
    assert _parse_audd_response(raw) is None


# ---------------------------------------------------------------------------
# SongMatch model
# ---------------------------------------------------------------------------


def test_song_match_bool_truthy() -> None:
    song = SongMatch(title="Song A", artist="Artist B")
    assert bool(song) is True


def test_song_match_bool_falsy() -> None:
    song = SongMatch()
    assert bool(song) is False


def test_song_match_to_dict() -> None:
    song = SongMatch(title="T", artist="A", confidence=0.95)
    d = song.to_dict()
    assert d["title"] == "T"
    assert d["artist"] == "A"
    assert abs(d["confidence"] - 0.95) < 0.01


# ---------------------------------------------------------------------------
# MusicIdentifyResult model
# ---------------------------------------------------------------------------


def test_music_identify_result_to_dict_no_match() -> None:
    result = MusicIdentifyResult(matched=False, error="no audio")
    d = result.to_dict()
    assert d["matched"] is False
    assert d["song"] is None
    assert d["error"] == "no audio"


def test_music_identify_result_to_dict_matched() -> None:
    song = SongMatch(title="X", artist="Y", confidence=0.9)
    result = MusicIdentifyResult(matched=True, song=song, latency_ms=220.5)
    d = result.to_dict()
    assert d["matched"] is True
    assert d["song"]["title"] == "X"
    assert d["latency_ms"] == 220.5


# ---------------------------------------------------------------------------
# identify_ambient_audio (unit, mocked sounddevice + httpx)
# ---------------------------------------------------------------------------


def _mock_capture(duration_s, sample_rate, channels, device):
    """Return a non-silent sine wave buffer."""
    t = np.linspace(0, duration_s, int(duration_s * sample_rate), dtype=np.float32)
    return np.sin(2 * np.pi * 440 * t), duration_s


def _audd_success_response():
    return {
        "status": "success",
        "result": {
            "title": "Test Song",
            "artist": "Test Artist",
            "album": "Test Album",
            "release_date": "2023-01-01",
            "label": "Test Label",
        },
    }


@pytest.mark.asyncio
async def test_identify_ambient_audio_success() -> None:
    """Full pipeline: capture → encode → mock API → parse match."""
    mock_post = MagicMock()
    mock_post.return_value.__enter__ = lambda s: s
    mock_post.return_value.__exit__ = MagicMock(return_value=False)

    with (
        patch("emily.voice.music_id._capture_audio", side_effect=_mock_capture),
        patch("emily.voice.music_id._call_audd_api", return_value=_audd_success_response()),
    ):
        result = identify_ambient_audio(duration_s=2, api_token="test-token")

    assert result.matched is True
    assert result.song is not None
    assert result.song.title == "Test Song"
    assert result.song.artist == "Test Artist"
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_identify_ambient_audio_no_match() -> None:
    with (
        patch("emily.voice.music_id._capture_audio", side_effect=_mock_capture),
        patch("emily.voice.music_id._call_audd_api", return_value={"status": "success", "result": None}),
    ):
        result = identify_ambient_audio(duration_s=2, api_token="test-token")

    assert result.matched is False
    assert result.song is None
    assert "No song matched" in result.error or result.error != ""


@pytest.mark.asyncio
async def test_identify_ambient_audio_api_error() -> None:
    with (
        patch("emily.voice.music_id._capture_audio", side_effect=_mock_capture),
        patch("emily.voice.music_id._call_audd_api", side_effect=Exception("Network timeout")),
    ):
        result = identify_ambient_audio(duration_s=2, api_token="test-token")

    assert result.matched is False
    assert "Network timeout" in result.error


def test_identify_ambient_audio_silence_gated() -> None:
    """Silence with zero duration should be gated without calling API."""
    def silent_capture(duration_s, sample_rate, channels, device):
        return np.zeros(100, dtype=np.float32), 0.0  # actual_duration=0 → silence

    with (
        patch("emily.voice.music_id._capture_audio", side_effect=silent_capture),
        patch("emily.voice.music_id._call_audd_api") as mock_api,
    ):
        result = identify_ambient_audio(duration_s=2)

    mock_api.assert_not_called()
    assert result.matched is False
    assert "No microphone input" in result.error


# ---------------------------------------------------------------------------
# MusicIdentifier async wrapper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_music_identifier_async() -> None:
    identifier = MusicIdentifier(api_token="test")
    with (
        patch("emily.voice.music_id._capture_audio", side_effect=_mock_capture),
        patch("emily.voice.music_id._call_audd_api", return_value=_audd_success_response()),
    ):
        result = await identifier.identify_async(duration_s=2)

    assert result.matched is True
    assert identifier.last_result() is result


@pytest.mark.asyncio
async def test_music_identifier_last_result_none_initially() -> None:
    identifier = MusicIdentifier()
    assert identifier.last_result() is None
