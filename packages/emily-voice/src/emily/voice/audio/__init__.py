"""Audio I/O package."""

from emily.voice.audio.capture import AudioCapture
from emily.voice.audio.interruption import InterruptionController
from emily.voice.audio.playback import AudioPlayback
from emily.voice.audio.processing import normalize, resample, silence, trim_silence

__all__ = [
    "AudioCapture",
    "AudioPlayback",
    "InterruptionController",
    "normalize",
    "resample",
    "silence",
    "trim_silence",
]
