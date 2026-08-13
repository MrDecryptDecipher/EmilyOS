"""Voice domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VoiceTurnState(StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    PROCESSING = "processing"
    ERROR = "error"


class SpeechStyle(StrEnum):
    NEUTRAL = "neutral"
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    WARM = "warm"
    EXCITED = "excited"
    CONCERNED = "concerned"
    CALM = "calm"
    TECHNICAL = "technical"
    EMPATHETIC = "empathetic"
    CASUAL = "casual"


class PauseProfile(StrEnum):
    NONE = "none"
    MICRO = "micro"
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    NATURAL = "natural"


class SpeechSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    pause_after: PauseProfile = PauseProfile.NATURAL
    emphasis: list[str] = Field(default_factory=list)
    language: str | None = None


class SpeechPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    language: str = "en"
    secondary_language: str | None = None
    code_switching: bool = False
    style: SpeechStyle = SpeechStyle.WARM
    emotion: str = "neutral"
    energy: float = 0.55
    pace: float = 1.0
    pitch: float = 0.0
    pause_profile: PauseProfile = PauseProfile.NATURAL
    emphasis: list[str] = Field(default_factory=list)
    pronunciation_hints: dict[str, str] = Field(default_factory=dict)
    voice: str | None = None
    tts_backend: str | None = None
    segments: list[SpeechSegment] = Field(default_factory=list)


class LanguageState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dominant: str = "en"
    secondary: str | None = None
    confidence: float = 0.5
    code_switching: bool = False
    # Alias-style fields for conversation continuity contracts
    detected_language: str | None = None
    user_language_preference: str | None = None
    # When True, LanguageDetector only flips dominant after a confident margin.
    sticky: bool = True
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AudioChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    samples: list[float] | bytes
    sample_rate: int = 24000
    channels: int = 1
    backend: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TTSCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    languages: list[str] = Field(default_factory=list)
    streaming: bool = False
    lightweight: bool = False
    priority: int = 100
    expressive: bool = False
    multilingual: bool = False
    notes: str = ""


class VoicePersonality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "Emily"
    warmth: float = 0.72
    energy: float = 0.55
    formality: float = 0.35
    expressiveness: float = 0.62
    speaking_rate: float = 0.96
    default_language: str = "en-IN"
    default_style: SpeechStyle = SpeechStyle.WARM
    voice_name: str | None = "emily-default"
    pronunciation_hints: dict[str, str] = Field(default_factory=dict)


class VoiceMetricsSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vad_latency_ms: float = 0.0
    asr_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0
    tts_latency_ms: float = 0.0
    ttfa_ms: float = 0.0
    asr_rtf: float = 0.0
    tts_rtf: float = 0.0
    memory_mb: float | None = None
    end_to_end_ms: float = 0.0
    turns: int = 0
    barge_ins: int = 0
    errors: int = 0
    last_backend: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class HardwareProfile(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class HardwareInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu_count: int = 1
    ram_gb: float = 0.0
    cuda_available: bool = False
    cuda_device_name: str | None = None
    mps_available: bool = False
    vram_gb: float | None = None
    # Reserved for future ONNX Runtime routing; False until wired.
    onnx_hint: bool = False
    profile: HardwareProfile = HardwareProfile.LOW


class ModelStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    installed: bool = False
    loaded: bool = False
    path: str | None = None
    size_hint: str | None = None
    download_instructions: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class VoiceStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    started: bool = False
    state: VoiceTurnState = VoiceTurnState.IDLE
    backends: dict[str, bool] = Field(default_factory=dict)
    hardware: HardwareInfo | None = None
    metrics: VoiceMetricsSnapshot | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
