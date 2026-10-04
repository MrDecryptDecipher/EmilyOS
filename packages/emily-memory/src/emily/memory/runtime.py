"""Memory runtime facade — store, retrieve, world, consolidate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from emily.core.types.memory import MemoryKind
from emily.memory.consolidator import MemoryConsolidator
from emily.memory.models import (
    ConsolidationResult,
    MemoryQuery,
    MemoryRecord,
    MemoryWrite,
    RetrievalHit,
    WorldObservation,
    WorldSnapshot,
)
from emily.memory.retriever import LexicalRetriever
from emily.memory.store import MemoryStore
from emily.memory.world import WorldModel


class MemoryRuntime:
    """Primary API for memory + world-model operations."""

    def __init__(
        self,
        memory_root: Path | str,
        world_root: Path | str | None = None,
        *,
        event_bus: Any | None = None,
        logger: Any | None = None,
        default_limit: int = 8,
    ) -> None:
        self.store = MemoryStore(memory_root)
        self.retriever = LexicalRetriever(self.store)
        self.world = WorldModel(world_root)
        self.consolidator = MemoryConsolidator(self.store)
        self.event_bus = event_bus
        self.logger = logger
        self.default_limit = default_limit
        self._started = False

    async def start(self) -> None:
        await self.world.load()
        self._started = True

    async def stop(self) -> None:
        await self.world.save()
        self._started = False

    async def put(self, write: MemoryWrite) -> MemoryRecord:
        record = await self.store.write(write)
        await self._emit(
            "memory.written",
            {
                "memory_id": record.memory_id,
                "kind": record.kind.value,
                "importance": record.importance,
                "mission_id": record.mission_id,
            },
        )
        if self.logger is not None:
            self.logger.info(
                "memory written",
                memory_id=record.memory_id,
                kind=record.kind.value,
            )
        return record

    async def get(self, memory_id: str, *, kind: MemoryKind | None = None) -> MemoryRecord:
        record = await self.store.get(memory_id, kind=kind)
        record.touch_access()
        await self.store.save(record)
        return record

    async def delete(self, memory_id: str, *, kind: MemoryKind | None = None) -> bool:
        return await self.store.delete(memory_id, kind=kind)

    async def search(self, query: MemoryQuery) -> list[RetrievalHit]:
        if query.limit <= 0:
            query = query.model_copy(update={"limit": self.default_limit})
        hits = await self.retriever.search(query)
        await self._emit(
            "memory.retrieved",
            {
                "query": query.text,
                "hits": len(hits),
                "kinds": [k.value for k in query.kinds] if query.kinds else ["*"],
            },
        )
        return hits

    async def remember(
        self,
        content: str,
        *,
        kind: MemoryKind = MemoryKind.WORKING,
        title: str = "",
        importance: float = 0.5,
        tags: list[str] | None = None,
        mission_id: str | None = None,
        agent_id: str | None = None,
        source: str = "manual",
    ) -> MemoryRecord:
        return await self.put(
            MemoryWrite(
                kind=kind,
                content=content,
                title=title,
                importance=importance,
                tags=list(tags or []),
                mission_id=mission_id,
                agent_id=agent_id,
                source=source,
            )
        )

    async def consolidate(self, *, prune_ephemeral: bool = True) -> ConsolidationResult:
        result = await self.consolidator.run(prune_ephemeral=prune_ephemeral)
        await self._emit(
            "memory.consolidated",
            {
                "scanned": result.scanned,
                "promoted": result.promoted,
                "pruned": result.pruned,
            },
        )
        return result

    async def observe(self, observation: WorldObservation) -> WorldSnapshot:
        snap = await self.world.observe(observation)
        # Mirror observation into environment_state memory for retrieval.
        await self.remember(
            observation.text,
            kind=MemoryKind.ENVIRONMENT_STATE,
            title="World observation",
            importance=min(1.0, observation.confidence),
            tags=["world", observation.source],
            mission_id=observation.mission_id,
            source="world",
        )
        await self._emit(
            "world.updated",
            {
                "entities": snap.metadata.get("entity_count", 0),
                "relations": snap.metadata.get("relation_count", 0),
                "facts": snap.metadata.get("fact_count", 0),
                "source": observation.source,
            },
        )
        return snap

    def world_snapshot(self) -> WorldSnapshot:
        return self.world.snapshot()

    async def stats(self) -> dict[str, Any]:
        counts = await self.store.count_by_kind()
        snap = self.world.snapshot()
        return {
            "memory_by_kind": counts,
            "memory_total": sum(counts.values()),
            "world_entities": snap.metadata.get("entity_count", 0),
            "world_relations": snap.metadata.get("relation_count", 0),
            "world_facts": snap.metadata.get("fact_count", 0),
        }

    async def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.event_bus is None:
            return
        await self.event_bus.publish(event_type, payload, source="memory")
