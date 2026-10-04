"""File-backed mission archive."""

from __future__ import annotations

import asyncio
from pathlib import Path

import orjson

from emily.missions.errors import MissionNotFoundError
from emily.missions.models import Mission


class MissionStore:
    """Persists missions as JSON documents under a root directory."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def _path(self, mission_id: str) -> Path:
        safe = mission_id.replace("/", "_").replace("\\", "_")
        return self.root / f"{safe}.json"

    async def save(self, mission: Mission) -> None:
        mission.touch()
        payload = mission.model_dump(mode="json")
        path = self._path(mission.mission_id)
        async with self._lock:
            await asyncio.to_thread(
                path.write_bytes, orjson.dumps(payload, option=orjson.OPT_INDENT_2)
            )

    async def get(self, mission_id: str) -> Mission:
        path = self._path(mission_id)
        if not path.exists():
            raise MissionNotFoundError(mission_id)
        raw = await asyncio.to_thread(path.read_bytes)
        return Mission.model_validate(orjson.loads(raw))

    async def list_missions(self) -> list[Mission]:
        files = sorted(self.root.glob("*.json"))
        missions: list[Mission] = []
        for path in files:
            raw = await asyncio.to_thread(path.read_bytes)
            missions.append(Mission.model_validate(orjson.loads(raw)))
        missions.sort(key=lambda m: m.updated_at, reverse=True)
        return missions

    async def delete(self, mission_id: str) -> None:
        path = self._path(mission_id)
        async with self._lock:
            if path.exists():
                await asyncio.to_thread(path.unlink)
