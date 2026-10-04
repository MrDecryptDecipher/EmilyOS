"""Extended mission store tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from emily.missions.models import Mission
from emily.missions.store import MissionStore


@pytest.mark.asyncio
async def test_store_delete_and_ordering(tmp_path: Path) -> None:
    store = MissionStore(tmp_path)
    first = Mission(goal="first")
    second = Mission(goal="second")
    await store.save(first)
    await asyncio.sleep(0.02)
    await store.save(second)
    listed = await store.list_missions()
    assert [m.goal for m in listed] == ["second", "first"]
    await store.delete(first.mission_id)
    remaining = await store.list_missions()
    assert len(remaining) == 1
    assert remaining[0].goal == "second"
    await store.delete("mis_does_not_exist")  # no-op


@pytest.mark.asyncio
async def test_store_overwrite_updates_timestamp(tmp_path: Path) -> None:
    store = MissionStore(tmp_path)
    mission = Mission(goal="mutable")
    await store.save(mission)
    original = (await store.get(mission.mission_id)).updated_at
    await asyncio.sleep(0.02)
    mission.goal = "mutated"
    await store.save(mission)
    loaded = await store.get(mission.mission_id)
    assert loaded.goal == "mutated"
    assert loaded.updated_at >= original
