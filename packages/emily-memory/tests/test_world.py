"""World model tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from emily.memory.models import ObservedRelation, WorldObservation
from emily.memory.world import WorldModel


@pytest.mark.asyncio
async def test_observe_entities_relations_and_persist(tmp_path: Path) -> None:
    world = WorldModel(tmp_path / "world")
    await world.load()
    snap = await world.observe(
        WorldObservation(
            text="AcmeCorp uses NVIDIA accelerators in production",
            entities=["AcmeCorp", "NVIDIA"],
            relations=[
                ObservedRelation(subject="AcmeCorp", predicate="uses", object="NVIDIA"),
            ],
            source="test",
            confidence=0.8,
        )
    )
    assert snap.metadata["entity_count"] == 2
    assert snap.metadata["relation_count"] == 1
    assert snap.metadata["fact_count"] == 1
    assert world.get_entity("AcmeCorp") is not None

    # reload
    world2 = WorldModel(tmp_path / "world")
    await world2.load()
    assert world2.get_entity("NVIDIA") is not None
    assert len(world2.list_entities()) == 2


@pytest.mark.asyncio
async def test_observe_extracts_names_when_unspecified(tmp_path: Path) -> None:
    world = WorldModel(tmp_path / "w")
    snap = await world.observe(
        WorldObservation(text="EmilyOS tracks Contoso and Fabrikam accounts")
    )
    names = {e.name for e in snap.entities}
    assert "EmilyOS" in names or "Contoso" in names
