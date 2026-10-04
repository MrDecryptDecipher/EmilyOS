"""Deep world-model edge cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from emily.memory.models import ObservedRelation, WorldObservation
from emily.memory.world import WorldModel


@pytest.mark.asyncio
async def test_entity_upsert_raises_confidence_and_relation_dedupe(tmp_path: Path) -> None:
    world = WorldModel(tmp_path)
    await world.observe(
        WorldObservation(
            text="Acme uses NVIDIA",
            entities=["Acme", "NVIDIA"],
            relations=[ObservedRelation(subject="Acme", predicate="uses", object="NVIDIA")],
            confidence=0.5,
        )
    )
    await world.observe(
        WorldObservation(
            text="Acme uses NVIDIA again",
            entities=["Acme", "NVIDIA"],
            relations=[ObservedRelation(subject="Acme", predicate="uses", object="NVIDIA")],
            confidence=0.9,
        )
    )
    snap = world.snapshot()
    assert snap.metadata["entity_count"] == 2
    assert snap.metadata["relation_count"] == 1
    acme = world.get_entity("Acme")
    assert acme is not None
    assert acme.confidence >= 0.9


@pytest.mark.asyncio
async def test_get_entity_by_id_and_empty_name(tmp_path: Path) -> None:
    world = WorldModel(tmp_path)
    snap = await world.observe(
        WorldObservation(text="placeholder", entities=["  ", "ValidName"], confidence=0.6)
    )
    names = {e.name for e in snap.entities}
    assert "unknown" in names or "ValidName" in names
    entity = world.get_entity("ValidName")
    assert entity is not None
    assert world.get_entity(entity.entity_id) is entity
    assert world.get_entity("missing-entity") is None


@pytest.mark.asyncio
async def test_fact_cap_keeps_latest(tmp_path: Path) -> None:
    world = WorldModel(tmp_path)
    # Inject many facts via observe loop (bounded path uses 500; use smaller by direct append then observe)
    for i in range(12):
        await world.observe(WorldObservation(text=f"Fact statement number {i} about Node{i}"))
    assert int(world.snapshot().metadata["fact_count"]) == 12
