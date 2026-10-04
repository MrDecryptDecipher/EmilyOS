"""Promote ephemeral memories into durable kinds."""

from __future__ import annotations

from emily.core.types.memory import MemoryKind
from emily.memory.models import ConsolidationResult, MemoryWrite
from emily.memory.store import MemoryStore

_EPHEMERAL = {MemoryKind.WORKING, MemoryKind.TASK}
_PROMOTE_TO = {
    MemoryKind.WORKING: MemoryKind.LONG_TERM,
    MemoryKind.TASK: MemoryKind.EPISODIC,
}


class MemoryConsolidator:
    """Rule-based consolidator for offline / default runtime."""

    def __init__(self, store: MemoryStore, *, min_importance: float = 0.55) -> None:
        self.store = store
        self.min_importance = min_importance

    async def run(self, *, prune_ephemeral: bool = True) -> ConsolidationResult:
        result = ConsolidationResult()
        for kind in _EPHEMERAL:
            records = await self.store.list_kind(kind, limit=1000)
            result.scanned += len(records)
            for record in records:
                if record.importance < self.min_importance and record.access_count < 1:
                    if prune_ephemeral:
                        await self.store.delete(record.memory_id, kind=kind)
                        result.pruned += 1
                    continue
                target = _PROMOTE_TO[kind]
                promoted = await self.store.write(
                    MemoryWrite(
                        kind=target,
                        content=record.content,
                        title=record.title or f"Promoted from {kind.value}",
                        importance=min(1.0, record.importance + 0.05),
                        tags=list({*record.tags, "consolidated", kind.value}),
                        mission_id=record.mission_id,
                        agent_id=record.agent_id,
                        source="consolidator",
                        metadata={
                            **record.metadata,
                            "promoted_from": record.memory_id,
                            "promoted_from_kind": kind.value,
                        },
                    )
                )
                result.promoted += 1
                result.promoted_ids.append(promoted.memory_id)
                if prune_ephemeral:
                    await self.store.delete(record.memory_id, kind=kind)
                    result.pruned += 1
        return result
