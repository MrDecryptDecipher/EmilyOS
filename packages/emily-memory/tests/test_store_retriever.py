"""Memory store, retrieval, and consolidation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from emily.core.types.memory import MemoryKind
from emily.memory.errors import MemoryNotFoundError
from emily.memory.models import MemoryQuery, MemoryWrite
from emily.memory.runtime import MemoryRuntime


@pytest.mark.asyncio
async def test_write_get_delete_and_search(tmp_path: Path) -> None:
    runtime = MemoryRuntime(tmp_path / "mem", tmp_path / "world")
    await runtime.start()
    a = await runtime.remember(
        "NVIDIA NIM endpoint is healthy",
        kind=MemoryKind.SEMANTIC,
        title="Provider health",
        importance=0.8,
        tags=["nvidia", "provider"],
    )
    await runtime.remember(
        "RoutesMe returned intermittent 429",
        kind=MemoryKind.FAILURE_HISTORY,
        title="Provider flake",
        importance=0.7,
        tags=["routesme"],
    )
    loaded = await runtime.get(a.memory_id)
    assert loaded.access_count == 1
    hits = await runtime.search(MemoryQuery(text="NVIDIA provider health", limit=5))
    assert hits
    assert hits[0].record.memory_id == a.memory_id
    assert await runtime.delete(a.memory_id) is True
    with pytest.raises(MemoryNotFoundError):
        await runtime.get(a.memory_id)
    await runtime.stop()


@pytest.mark.asyncio
async def test_consolidation_promotes_working(tmp_path: Path) -> None:
    runtime = MemoryRuntime(tmp_path / "mem", tmp_path / "world")
    await runtime.start()
    await runtime.put(
        MemoryWrite(
            kind=MemoryKind.WORKING,
            content="Important working note about Emily missions",
            title="Working note",
            importance=0.9,
            tags=["temp"],
        )
    )
    await runtime.put(
        MemoryWrite(
            kind=MemoryKind.WORKING,
            content="noise",
            title="low",
            importance=0.1,
        )
    )
    result = await runtime.consolidate()
    assert result.promoted >= 1
    assert result.pruned >= 1
    long_term = await runtime.store.list_kind(MemoryKind.LONG_TERM)
    assert any("Emily missions" in r.content for r in long_term)
    working = await runtime.store.list_kind(MemoryKind.WORKING)
    assert working == []
    await runtime.stop()


@pytest.mark.asyncio
async def test_kind_filter_and_stats(tmp_path: Path) -> None:
    runtime = MemoryRuntime(tmp_path / "mem", tmp_path / "world")
    await runtime.start()
    await runtime.remember("alpha topic", kind=MemoryKind.EPISODIC, title="A")
    await runtime.remember("beta topic", kind=MemoryKind.PREFERENCES, title="B")
    hits = await runtime.search(
        MemoryQuery(text="topic", kinds=[MemoryKind.PREFERENCES], limit=10)
    )
    assert len(hits) == 1
    assert hits[0].record.kind == MemoryKind.PREFERENCES
    stats = await runtime.stats()
    assert stats["memory_total"] >= 2
    await runtime.stop()
