"""Continuous world model — entities, relations, facts."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from emily.memory.models import (
    ObservedRelation,
    WorldEntity,
    WorldFact,
    WorldObservation,
    WorldRelation,
    WorldSnapshot,
)

_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{1,40}")


class WorldModel:
    """Process-local world graph with optional file persistence."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else None
        if self.root is not None:
            self.root.mkdir(parents=True, exist_ok=True)
        self._entities: dict[str, WorldEntity] = {}
        self._by_name: dict[str, str] = {}
        self._relations: list[WorldRelation] = []
        self._facts: list[WorldFact] = []
        self._lock = asyncio.Lock()

    async def load(self) -> None:
        if self.root is None:
            return
        path = self.root / "snapshot.json"
        if not path.exists():
            return
        raw = await asyncio.to_thread(path.read_text, "utf-8")
        snap = WorldSnapshot.model_validate(json.loads(raw))
        self._entities = {e.entity_id: e for e in snap.entities}
        self._by_name = {e.name.lower(): e.entity_id for e in snap.entities}
        self._relations = list(snap.relations)
        self._facts = list(snap.facts)

    async def save(self) -> None:
        if self.root is None:
            return
        snap = self.snapshot()
        path = self.root / "snapshot.json"
        payload = snap.model_dump(mode="json")
        async with self._lock:
            await asyncio.to_thread(path.write_text, json.dumps(payload, indent=2), "utf-8")

    def snapshot(self) -> WorldSnapshot:
        return WorldSnapshot(
            entities=list(self._entities.values()),
            relations=list(self._relations),
            facts=list(self._facts),
            metadata={
                "entity_count": len(self._entities),
                "relation_count": len(self._relations),
                "fact_count": len(self._facts),
            },
        )

    def list_entities(self) -> list[WorldEntity]:
        return sorted(self._entities.values(), key=lambda e: e.name.lower())

    def get_entity(self, name_or_id: str) -> WorldEntity | None:
        if name_or_id in self._entities:
            return self._entities[name_or_id]
        eid = self._by_name.get(name_or_id.lower())
        return self._entities.get(eid) if eid else None

    async def observe(self, observation: WorldObservation) -> WorldSnapshot:
        async with self._lock:
            names = list(observation.entities)
            if not names:
                names = _extract_names(observation.text)
            entity_ids: list[str] = []
            for name in names:
                entity = self._upsert_entity(
                    name,
                    entity_type=observation.entity_type,
                    confidence=observation.confidence,
                )
                entity_ids.append(entity.entity_id)

            for rel in observation.relations:
                self._upsert_relation(rel, confidence=observation.confidence)

            if observation.text.strip():
                self._facts.append(
                    WorldFact(
                        statement=observation.text.strip(),
                        entity_ids=entity_ids,
                        confidence=observation.confidence,
                        source=observation.source,
                    )
                )
                if len(self._facts) > 500:
                    self._facts = self._facts[-500:]

        await self.save()
        return self.snapshot()

    def _upsert_entity(
        self,
        name: str,
        *,
        entity_type: str,
        confidence: float,
    ) -> WorldEntity:
        key = name.strip() or "unknown"
        existing_id = self._by_name.get(key.lower())
        if existing_id and existing_id in self._entities:
            entity = self._entities[existing_id]
            entity.confidence = max(entity.confidence, confidence)
            entity.entity_type = entity_type or entity.entity_type
            entity.updated_at = datetime.now(UTC)
            return entity
        entity = WorldEntity(
            name=key,
            entity_type=entity_type,
            confidence=confidence,
        )
        self._entities[entity.entity_id] = entity
        self._by_name[key.lower()] = entity.entity_id
        return entity

    def _upsert_relation(self, rel: ObservedRelation, *, confidence: float) -> None:
        subject = self._upsert_entity(rel.subject, entity_type="thing", confidence=confidence)
        obj = self._upsert_entity(rel.object, entity_type="thing", confidence=confidence)
        for existing in self._relations:
            if (
                existing.subject_id == subject.entity_id
                and existing.object_id == obj.entity_id
                and existing.predicate.lower() == rel.predicate.lower()
            ):
                existing.confidence = max(existing.confidence, confidence)
                existing.updated_at = datetime.now(UTC)
                return
        self._relations.append(
            WorldRelation(
                subject_id=subject.entity_id,
                predicate=rel.predicate,
                object_id=obj.entity_id,
                confidence=confidence,
                evidence=f"{rel.subject} {rel.predicate} {rel.object}",
            )
        )


def _extract_names(text: str) -> list[str]:
    """Heuristic proper-noun / token extraction for offline observation."""
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "into",
        "about",
        "after",
        "before",
        "emily",
        "mission",
        "agent",
        "task",
    }
    found: list[str] = []
    for match in _NAME_RE.findall(text):
        if match.lower() in stop:
            continue
        if match[0].isupper() or "_" in match:
            if match not in found:
                found.append(match)
    return found[:12]
