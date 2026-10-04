"""Memory and world-model domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from emily.core.ids import new_id
from emily.core.types.memory import MemoryKind


def new_memory_id() -> str:
    return new_id("mem")


def new_entity_id() -> str:
    return new_id("ent")


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str = Field(default_factory=new_memory_id)
    kind: MemoryKind
    content: str
    title: str = ""
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    mission_id: str | None = None
    agent_id: str | None = None
    source: str = "manual"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    accessed_at: datetime | None = None
    access_count: int = 0

    def touch_access(self) -> None:
        self.accessed_at = datetime.now(UTC)
        self.access_count += 1
        self.updated_at = datetime.now(UTC)

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)


class MemoryWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: MemoryKind
    content: str
    title: str = ""
    importance: float = 0.5
    tags: list[str] = Field(default_factory=list)
    mission_id: str | None = None
    agent_id: str | None = None
    source: str = "manual"
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    kinds: list[MemoryKind] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    mission_id: str | None = None
    limit: int = Field(default=8, ge=1, le=100)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class RetrievalHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record: MemoryRecord
    score: float
    reasons: list[str] = Field(default_factory=list)


class WorldEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(default_factory=new_entity_id)
    name: str
    entity_type: str = "thing"
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorldRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str
    predicate: str
    object_id: str
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    evidence: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorldFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str = Field(default_factory=lambda: new_id("fact"))
    statement: str
    entity_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    source: str = "observe"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ObservedRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    predicate: str
    object: str


class WorldObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    entities: list[str] = Field(default_factory=list)
    entity_type: str = "thing"
    relations: list[ObservedRelation] = Field(default_factory=list)
    source: str = "manual"
    mission_id: str | None = None
    confidence: float = 0.7


class WorldSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: list[WorldEntity] = Field(default_factory=list)
    relations: list[WorldRelation] = Field(default_factory=list)
    facts: list[WorldFact] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConsolidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanned: int = 0
    promoted: int = 0
    pruned: int = 0
    promoted_ids: list[str] = Field(default_factory=list)
