"""Mission store tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from emily.missions.errors import MissionNotFoundError
from emily.missions.models import Mission
from emily.missions.store import MissionStore


@pytest.mark.asyncio
async def test_store_save_get_list(tmp_path: Path) -> None:
    store = MissionStore(tmp_path)
    mission = Mission(goal="Ship M2")
    await store.save(mission)
    loaded = await store.get(mission.mission_id)
    assert loaded.goal == "Ship M2"
    listed = await store.list_missions()
    assert len(listed) == 1


@pytest.mark.asyncio
async def test_store_missing(tmp_path: Path) -> None:
    store = MissionStore(tmp_path)
    with pytest.raises(MissionNotFoundError):
        await store.get("mis_missing")
