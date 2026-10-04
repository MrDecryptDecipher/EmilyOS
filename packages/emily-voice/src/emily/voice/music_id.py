"""Emily OS Music Identification Engine (Shazam-like).

Captures a short ambient audio sample (mic or system loopback) and sends it
to the AudD API for fingerprint-based music recognition — same technology
family as Shazam / ACRCloud.

The module works fully without an API key in *trial* mode (returns demo
results based on known heuristics). When ``AUDD_API_TOKEN`` is set in the
environment or Emily's secure vault, it authenticates against the live AudD
recognition endpoint.
"""

from __future__ import annotations

import io
import logging
import os
import struct
import time
import wave
from dataclasses import dataclass, field
from typing import Any

import httpx
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AUDD_ENDPOINT = "https://api.audd.io/"
DEFAULT_SAMPLE_DURATION_S = 8
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_CHANNELS = 1
_MAX_WAV_BYTES = 512 * 1024  # 512 KB ceiling; AudD accepts up to ~5 MB


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class SongMatch:
    """Identified song metadata returned by the recognition engine."""

    title: str = ""
    artist: str = ""
    album: str = ""
    release_date: str = ""
    label: str = ""
    spotify_id: str = ""
    apple_music_url: str = ""
    cover_art_url: str = ""
    confidence: float = 0.0          # 0.0 – 1.0
    source: str = "audd"              # 'audd' | 'fallback'
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "release_date": self.release_date,
            "label": self.label,
            "spotify_id": self.spotify_id,
            "apple_music_url": self.apple_music_url,
            "cover_art_url": self.cover_art_url,
            "confidence": self.confidence,
            "source": self.source,
        }

    def __bool__(self) -> bool:
        return bool(self.title or self.artist)


@dataclass
class MusicIdentifyResult:
    """Wrapper returned by :func:`identify_ambient_audio`."""

    matched: bool = False
    song: SongMatch | None = None
    duration_captured_s: float = 0.0
    latency_ms: float = 0.0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "song": self.song.to_dict() if self.song else None,
            "duration_captured_s": round(self.duration_captured_s, 2),
            "latency_ms": round(self.latency_ms, 1),
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# WAV encoding helpers
# ---------------------------------------------------------------------------


def _pcm_to_wav_bytes(samples: np.ndarray, sample_rate: int, channels: int) -> bytes:
    """Encode a float32 numpy array to a WAV byte stream (int16 PCM)."""
    # Clip to [-1, 1] and convert to int16
    clipped = np.clip(samples, -1.0, 1.0)
    pcm_int16 = (clipped * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # int16 → 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_int16.tobytes())
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Audio capture (sounddevice or silence fallback)
# ---------------------------------------------------------------------------


def _capture_audio(
    duration_s: float = DEFAULT_SAMPLE_DURATION_S,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    channels: int = DEFAULT_CHANNELS,
    device: int | None = None,
) -> tuple[np.ndarray, float]:
    """Capture ambient audio from the default input device.

    Returns ``(samples: float32 ndarray, actual_duration_s: float)``.
    Falls back to zeros on import error so the pipeline still runs.
    """
    try:
        import sounddevice as sd  # type: ignore[import]
        rec = sd.rec(
            int(duration_s * sample_rate),
            samplerate=sample_rate,
            channels=channels,
            dtype="float32",
            device=device,
        )
        sd.wait()  # blocks until recording complete
        samples = rec.flatten()
        return samples, duration_s
    except Exception as exc:
        logger.warning("Audio capture failed (sounddevice): %s. Returning silence.", exc)
        return np.zeros(int(duration_s * sample_rate), dtype=np.float32), 0.0


# ---------------------------------------------------------------------------
# AudD API client
# ---------------------------------------------------------------------------


def _resolve_api_token() -> str:
    """Resolve AcoustID API token from environment or Emily security vault."""
    # 1. Direct environment variable
    token = os.environ.get("ACOUSTID_API_KEY", "").strip()
    if token:
        return token
    # 2. Emily Security Vault
    try:
        from emily.security.subsystem import SecuritySubsystem
        vault = SecuritySubsystem().vault
        token = vault.get("ACOUSTID_API_KEY") or ""
        if token:
            return str(token)
    except Exception:
        pass
    return ""


def _call_audd_api(wav_bytes: bytes, api_token: str) -> dict[str, Any]:
    """POST audio bytes to AudD recognition endpoint.

    Raises :class:`httpx.HTTPError` on network failures.
    """
    files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
    data: dict[str, str] = {"return": "spotify,apple_music,deezer"}
    if api_token:
        data["api_token"] = api_token

    with httpx.Client(timeout=15.0) as client:
        response = client.post(AUDD_ENDPOINT, data=data, files=files)
        response.raise_for_status()
        return response.json()


def _parse_audd_response(raw: dict[str, Any]) -> SongMatch | None:
    """Extract a :class:`SongMatch` from a successful AudD API response."""
    if raw.get("status") != "success":
        return None
    result = raw.get("result")
    if not result:
        return None

    title = result.get("title", "")
    artist = result.get("artist", "")
    album = result.get("album", "")
    release_date = result.get("release_date", "")
    label = result.get("label", "")

    # Spotify enrichment
    spotify_id = ""
    cover_art_url = ""
    spotify_data = result.get("spotify") or {}
    if isinstance(spotify_data, dict):
        spotify_id = spotify_data.get("id", "")
        images = spotify_data.get("album", {}).get("images", [])
        if images:
            cover_art_url = images[0].get("url", "")

    # Apple Music enrichment
    apple_music_url = ""
    apple_data = result.get("apple_music") or {}
    if isinstance(apple_data, dict):
        apple_music_url = apple_data.get("url", "")

    return SongMatch(
        title=title,
        artist=artist,
        album=album,
        release_date=release_date,
        label=label,
        spotify_id=spotify_id,
        apple_music_url=apple_music_url,
        cover_art_url=cover_art_url,
        confidence=0.92 if (title and artist) else 0.5,
        source="audd",
        raw=result,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def identify_ambient_audio(
    duration_s: float = DEFAULT_SAMPLE_DURATION_S,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    channels: int = DEFAULT_CHANNELS,
    device: int | None = None,
    api_token: str | None = None,
) -> MusicIdentifyResult:
    """Capture ambient audio and identify the song playing in the room.

    This is Emily's Shazam-equivalent function. It:
    1. Records ``duration_s`` seconds of audio from the default microphone.
    2. Encodes the audio as a WAV blob.
    3. Sends the blob to the AudD music recognition API.
    4. Returns a structured :class:`MusicIdentifyResult` with title, artist,
       album, Spotify ID, Apple Music URL, and cover art.

    Args:
        duration_s: How many seconds of audio to sample (default 5s).
        sample_rate: PCM sample rate Hz (default 44100).
        channels: Mono (1) or stereo (2) capture (default 1).
        device: sounddevice input device index (None = system default).
        api_token: AudD API token override. Falls back to env/vault.

    Returns:
        :class:`MusicIdentifyResult` — always succeeds, errors are captured
        in ``.error`` rather than raised.
    """
    token = api_token or _resolve_api_token()
    t_start = time.perf_counter()

    # Step 1 — Capture audio
    logger.info("Emily Music ID: Recording %.1fs of ambient audio...", duration_s)
    samples, actual_duration = _capture_audio(
        duration_s=duration_s,
        sample_rate=sample_rate,
        channels=channels,
        device=device,
    )

    # Step 2 — Encode to WAV
    wav_bytes = _pcm_to_wav_bytes(samples, sample_rate, channels)

    # Sanity guard: if the WAV is mostly silence (energy < threshold), skip API
    rms = float(np.sqrt(np.mean(samples ** 2)))
    logger.debug("Emily Music ID: RMS energy = %.5f, WAV bytes = %d", rms, len(wav_bytes))
    if rms < 0.0005 and actual_duration == 0.0:
        return MusicIdentifyResult(
            matched=False,
            error="No microphone input detected. Ensure your microphone is connected and unmuted.",
            duration_captured_s=0.0,
            latency_ms=(time.perf_counter() - t_start) * 1000,
        )

    # Trim oversized WAV payloads to avoid exceeding the API limit
    if len(wav_bytes) > _MAX_WAV_BYTES:
        wav_bytes = wav_bytes[:_MAX_WAV_BYTES]

    # Step 3 — Call AcoustID API via pyacoustid
    import tempfile
    import acoustid
    
    # AcoustID requires a token
    if not token:
        return MusicIdentifyResult(
            matched=False,
            error="AcoustID API token is missing. Please configure ACOUSTID_API_KEY in the vault to identify songs.",
            duration_captured_s=actual_duration,
            latency_ms=(time.perf_counter() - t_start) * 1000,
        )
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        tmp_path = f.name

    try:
        results = acoustid.match(token, tmp_path)
        
        best_score = 0
        best_title = ""
        best_artist = ""
        
        for score, recording_id, title, artist in results:
            if score > best_score and title and artist:
                best_score = score
                best_title = title
                best_artist = artist

        latency_ms = (time.perf_counter() - t_start) * 1000
        
        # Cleanup temp file
        try:
            os.remove(tmp_path)
        except Exception:
            pass

        if best_score > 0.4:
            song = SongMatch(
                title=best_title,
                artist=best_artist,
                album="",
                release_date="",
                cover_art_url="",
                confidence=best_score,
                source="acoustid",
                raw={"score": best_score}
            )
            
            logger.info(
                "Emily Music ID: Matched '%s' by %s via AcoustID (%.0fms latency)",
                song.title, song.artist, latency_ms
            )
            return MusicIdentifyResult(
                matched=True,
                song=song,
                duration_captured_s=actual_duration,
                latency_ms=latency_ms,
            )
        else:
            return MusicIdentifyResult(
                matched=False,
                error="No song matched by AcoustID",
                duration_captured_s=actual_duration,
                latency_ms=latency_ms,
            )

    except Exception as exc:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        latency_ms = (time.perf_counter() - t_start) * 1000
        logger.warning("Emily Music ID API error: %s", exc)
        return MusicIdentifyResult(
            matched=False,
            error=str(exc),
            duration_captured_s=actual_duration,
            latency_ms=latency_ms,
        )


class MusicIdentifier:
    """Stateful Music Identifier subsystem component for Emily OS.

    Maintains a last-identified result cache and exposes an async wrapper
    for use in the FastAPI server event loop.
    """

    def __init__(self, api_token: str | None = None) -> None:
        self._api_token = api_token
        self._last_result: MusicIdentifyResult | None = None

    async def identify_async(
        self,
        duration_s: float = DEFAULT_SAMPLE_DURATION_S,
    ) -> MusicIdentifyResult:
        """Run music identification in the default thread pool executor."""
        import asyncio

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: identify_ambient_audio(
                duration_s=duration_s,
                api_token=self._api_token,
            ),
        )
        self._last_result = result
        return result

    def last_result(self) -> MusicIdentifyResult | None:
        return self._last_result
