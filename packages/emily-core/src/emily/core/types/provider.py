"""Provider enumerations."""

from enum import StrEnum


class ProviderKind(StrEnum):
    LLM = "llm"
    EMBEDDING = "embedding"
    STT = "stt"
    TTS = "tts"
    VISION = "vision"
    RERANK = "rerank"


class ProviderStatus(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
