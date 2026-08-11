"""Agent domain enumerations (runtime arrives in M3)."""

from enum import StrEnum


class AgentKind(StrEnum):
    RESEARCH = "research"
    CODING = "coding"
    VERIFICATION = "verification"
    DESKTOP = "desktop"
    BROWSER = "browser"
    VISION = "vision"
    VOICE = "voice"
    DOCUMENT = "document"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    TRADING = "trading"
    SECURITY = "security"
    WEB3 = "web3"
    AUTOMATION = "automation"
    DATA = "data"
    SCHEDULER = "scheduler"
    PRESENTATION = "presentation"
    EMAIL = "email"
    MEETING = "meeting"
    MONITORING = "monitoring"
    CUSTOM = "custom"


class AgentStatus(StrEnum):
    SPAWNING = "spawning"
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    FAILED = "failed"
    TERMINATED = "terminated"
