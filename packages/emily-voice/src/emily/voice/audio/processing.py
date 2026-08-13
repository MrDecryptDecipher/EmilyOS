"""Audio DSP helpers — float32 PCM, resample, normalize, trim, silence."""

from __future__ import annotations

import numpy as np

from emily.voice.models import AudioChunk
from emily.voice.speech.pauses import PauseProfile, pause_duration_ms


def ensure_float32_mono(samples: list[float] | bytes | np.ndarray, *, channels: int = 1) -> np.ndarray:
    if isinstance(samples, bytes):
        arr = np.frombuffer(samples, dtype=np.float32)
    else:
        arr = np.asarray(samples, dtype=np.float32)
    if arr.ndim > 1:
        arr = arr.mean(axis=1)
    elif channels > 1 and arr.size % channels == 0:
        arr = arr.reshape(-1, channels).mean(axis=1)
    return arr.astype(np.float32, copy=False)


def resample(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate or samples.size == 0:
        return samples.astype(np.float32, copy=False)
    duration = samples.size / float(src_rate)
    dst_len = max(1, round(duration * dst_rate))
    x_old = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=dst_len, endpoint=False)
    return np.interp(x_new, x_old, samples).astype(np.float32)


def normalize(samples: np.ndarray, *, peak: float = 0.95) -> np.ndarray:
    if samples.size == 0:
        return samples
    max_abs = float(np.max(np.abs(samples)))
    if max_abs < 1e-8:
        return samples.astype(np.float32, copy=False)
    return (samples * (peak / max_abs)).astype(np.float32)


def trim_silence(
    samples: np.ndarray,
    *,
    sample_rate: int,
    threshold: float = 0.01,
    pad_ms: float = 40.0,
) -> np.ndarray:
    if samples.size == 0:
        return samples
    mask = np.abs(samples) >= threshold
    if not np.any(mask):
        return samples[:0].astype(np.float32)
    idx = np.where(mask)[0]
    pad = int(sample_rate * pad_ms / 1000.0)
    start = max(0, int(idx[0]) - pad)
    end = min(samples.size, int(idx[-1]) + pad + 1)
    return samples[start:end].astype(np.float32, copy=False)


def silence(duration_ms: float, *, sample_rate: int, channels: int = 1) -> np.ndarray:
    n = max(0, int(sample_rate * duration_ms / 1000.0))
    if channels <= 1:
        return np.zeros(n, dtype=np.float32)
    return np.zeros((n, channels), dtype=np.float32)


def silence_for_pause(profile: PauseProfile, *, sample_rate: int) -> np.ndarray:
    return silence(pause_duration_ms(profile), sample_rate=sample_rate)


def fade(samples: np.ndarray, sample_rate: int, fade_ms: float = 8.0) -> np.ndarray:
    """Apply short linear fade-in/out to reduce clicks."""
    arr = np.asarray(samples, dtype=np.float32)
    if arr.size == 0 or fade_ms <= 0:
        return arr.astype(np.float32, copy=False)
    n = min(arr.size // 2, max(1, int(sample_rate * fade_ms / 1000.0)))
    if n <= 0:
        return arr.astype(np.float32, copy=False)
    out = arr.copy()
    ramp = np.linspace(0.0, 1.0, num=n, dtype=np.float32)
    out[:n] *= ramp
    out[-n:] *= ramp[::-1]
    return out


def apply_pace(samples: np.ndarray, pace: float) -> np.ndarray:
    """
    Adjust delivery speed.

    IMPORTANT: naive time-stretch also shifts pitch. We only allow mild speed-up
    (pace > 1); slowing (pace < 1) is a no-op so voices do not turn low/male.
    """
    arr = np.asarray(samples, dtype=np.float32)
    if arr.size == 0 or abs(pace - 1.0) < 0.02:
        return arr.astype(np.float32, copy=False)
    pace = max(0.92, min(1.08, float(pace)))
    if pace < 1.0:
        # Do not stretch slower — that drops pitch and sounds half-male.
        return arr.astype(np.float32, copy=False)
    new_len = max(1, int(arr.size / pace))
    x_old = np.linspace(0.0, 1.0, num=arr.size, endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=new_len, endpoint=False)
    return np.interp(x_new, x_old, arr).astype(np.float32)


def raise_pitch(samples: np.ndarray, *, semitones: float = 1.5) -> np.ndarray:
    """
    Raise pitch for a younger/sweeter female timbre.

    Uses resampling (slightly faster + higher). Prefer small shifts (1–2.5 st).
    """
    arr = np.asarray(samples, dtype=np.float32)
    if arr.size == 0 or abs(semitones) < 0.05:
        return arr.astype(np.float32, copy=False)
    semitones = max(-2.0, min(3.0, float(semitones)))
    factor = 2.0 ** (semitones / 12.0)
    new_len = max(1, int(round(arr.size / factor)))
    x_old = np.linspace(0.0, 1.0, num=arr.size, endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=new_len, endpoint=False)
    return np.interp(x_new, x_old, arr).astype(np.float32)


def postprocess_for_playback(
    chunk: AudioChunk,
    *,
    pace: float = 1.0,
    pitch_semitones: float = 0.0,
) -> AudioChunk:
    """Trim silence, optional pitch lift, normalize, and light fade before playback."""
    samples = ensure_float32_mono(chunk.samples, channels=chunk.channels)
    trimmed = trim_silence(samples, sample_rate=chunk.sample_rate)
    if trimmed.size == 0:
        trimmed = samples
    pitched = raise_pitch(trimmed, semitones=pitch_semitones) if pitch_semitones else trimmed
    paced = apply_pace(pitched, pace)
    normed = normalize(paced, peak=0.86)
    faded = fade(normed, chunk.sample_rate, fade_ms=8.0)
    return AudioChunk(
        samples=faded.tolist(),
        sample_rate=chunk.sample_rate,
        channels=1,
        backend=chunk.backend,
        metadata={**dict(chunk.metadata), "postprocessed": True},
    )


def chunk_rms(chunk: AudioChunk) -> float:
    """Root-mean-square level for mic sanity checks."""
    samples = ensure_float32_mono(chunk.samples, channels=chunk.channels)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples))))


def chunk_has_speech(chunk: AudioChunk, *, min_rms: float = 0.006) -> bool:
    """True when the recording has enough energy to be real speech (not silence/noise floor)."""
    return chunk_rms(chunk) >= min_rms


def to_pcm_bytes(samples: np.ndarray) -> bytes:
    return np.asarray(samples, dtype=np.float32).tobytes()
