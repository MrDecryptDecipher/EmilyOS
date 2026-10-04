"""File-backed multi-kind memory store."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from emily.core.types.memory import MemoryKind
from emily.memory.errors import MemoryNotFoundError
from emily.memory.models import MemoryRecord, MemoryWrite


class MemoryStore:
    """Persists memory records as JSON under ``{root}/{kind}/{id}.json``."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def _kind_dir(self, kind: MemoryKind) -> Path:
        path = self.root / kind.value
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _path(self, kind: MemoryKind, memory_id: str) -> Path:
        safe = memory_id.replace("/", "_").replace("\\", "_")
        return self._kind_dir(kind) / f"{safe}.json"

    async def write(self, spec: MemoryWrite) -> MemoryRecord:
        record = MemoryRecord(
            kind=spec.kind,
            content=spec.content,
            title=spec.title,
            importance=spec.importance,
            tags=list(spec.tags),
            mission_id=spec.mission_id,
            agent_id=spec.agent_id,
            source=spec.source,
            metadata=dict(spec.metadata),
        )
        await self.save(record)
        return record

    async def save(self, record: MemoryRecord) -> None:
        record.touch()
        path = self._path(record.kind, record.memory_id)
        payload = record.model_dump(mode="json")
        async with self._lock:
            await asyncio.to_thread(path.write_text, json.dumps(payload, indent=2), "utf-8")

    async def get(self, memory_id: str, *, kind: MemoryKind | None = None) -> MemoryRecord:
        if kind is not None:
            path = self._path(kind, memory_id)
            if not path.exists():
                raise MemoryNotFoundError(memory_id)
            return await self._load(path)
        for candidate in MemoryKind:
            path = self._path(candidate, memory_id)
            if path.exists():
                return await self._load(path)
        raise MemoryNotFoundError(memory_id)

    async def delete(self, memory_id: str, *, kind: MemoryKind | None = None) -> bool:
        async with self._lock:
            if kind is not None:
                path = self._path(kind, memory_id)
                if path.exists():
                    await asyncio.to_thread(path.unlink)
                    return True
                return False
            deleted = False
            for candidate in MemoryKind:
                path = self._path(candidate, memory_id)
                if path.exists():
                    await asyncio.to_thread(path.unlink)
                    deleted = True
            return deleted

    async def list_kind(self, kind: MemoryKind, *, limit: int = 500) -> list[MemoryRecord]:
        files = sorted(
            self._kind_dir(kind).glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        records: list[MemoryRecord] = []
        for path in files[: max(0, limit)]:
            records.append(await self._load(path))
        return records

    async def list_all(self, *, limit_per_kind: int = 200) -> list[MemoryRecord]:
        records: list[MemoryRecord] = []
        for kind in MemoryKind:
            records.extend(await self.list_kind(kind, limit=limit_per_kind))
        records.sort(key=lambda r: r.updated_at, reverse=True)
        return records

    async def count_by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for kind in MemoryKind:
            counts[kind.value] = len(list(self._kind_dir(kind).glob("*.json")))
        return counts

    async def _load(self, path: Path) -> MemoryRecord:
        raw = await asyncio.to_thread(path.read_text, "utf-8")
        return MemoryRecord.model_validate(json.loads(raw))
