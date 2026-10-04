"""Deep unit coverage for M4 memory store, retrieval, consolidation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from emily.core.types.memory import MemoryKind
from emily.memory.errors import MemoryNotFoundError
from emily.memory.models import MemoryQuery, MemoryRecord, MemoryWrite
from emily.memory.retriever import LexicalRetriever, tokenize
from emily.memory.runtime import MemoryRuntime
from emily.memory.store import MemoryStore


@pytest.mark.asyncio
async def test_store_kind_scoped_get_and_delete(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    rec = await store.write(
        MemoryWrite(kind=MemoryKind.SEMANTIC, content="alpha knowledge", title="Alpha")
    )
    got = await store.get(rec.memory_id, kind=MemoryKind.SEMANTIC)
    assert got.content == "alpha knowledge"
    with pytest.raises(MemoryNotFoundError):
        await store.get(rec.memory_id, kind=MemoryKind.WORKING)
    assert await store.delete("missing") is False
    assert await store.delete(rec.memory_id, kind=MemoryKind.SEMANTIC) is True
    assert await store.delete(rec.memory_id) is False


@pytest.mark.asyncio
async def test_store_concurrent_writes(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)

    async def one(i: int) -> MemoryRecord:
        return await store.write(
            MemoryWrite(
                kind=MemoryKind.WORKING,
                content=f"note-{i} concurrent memory payload",
                title=f"N{i}",
                importance=0.5,
            )
        )

    records = await asyncio.gather(*(one(i) for i in range(20)))
    assert len({r.memory_id for r in records}) == 20
    listed = await store.list_kind(MemoryKind.WORKING)
    assert len(listed) == 20


@pytest.mark.asyncio
async def test_retrieval_ranking_title_tags_mission_min_score(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    await store.write(
        MemoryWrite(
            kind=MemoryKind.SEMANTIC,
            content="generic notes about systems",
            title="Unrelated",
            importance=0.2,
            tags=["other"],
        )
    )
    target = await store.write(
        MemoryWrite(
            kind=MemoryKind.SEMANTIC,
            content="details about Contoso billing pipeline",
            title="Contoso billing",
            importance=0.9,
            tags=["contoso", "billing"],
            mission_id="mis_1",
        )
    )
    # Older low-signal record with overlapping tokens
    old = MemoryRecord(
        kind=MemoryKind.EPISODIC,
        content="billing pipeline archive",
        title="Archive",
        importance=0.4,
        tags=["billing"],
        mission_id="mis_1",
        updated_at=datetime.now(UTC) - timedelta(days=40),
    )
    await store.save(old)

    retriever = LexicalRetriever(store)
    hits = await retriever.search(
        MemoryQuery(
            text="Contoso billing",
            tags=["contoso"],
            mission_id="mis_1",
            limit=5,
            min_score=0.2,
        )
    )
    assert hits
    assert hits[0].record.memory_id == target.memory_id
    assert any("title_match" in h.reasons or "tokens:" in ",".join(h.reasons) for h in hits)

    empty = await retriever.search(
        MemoryQuery(text="zzzz-no-match-token", min_score=0.95, limit=5)
    )
    assert empty == []


def test_tokenize_filters_short_tokens() -> None:
    assert "ab" in tokenize("ab cd_ef")
    assert "a" not in tokenize("a bb")


@pytest.mark.asyncio
async def test_task_consolidation_to_episodic(tmp_path: Path) -> None:
    runtime = MemoryRuntime(tmp_path / "m", tmp_path / "w")
    await runtime.start()
    await runtime.put(
        MemoryWrite(
            kind=MemoryKind.TASK,
            content="Completed Contoso onboarding checklist",
            title="Task done",
            importance=0.8,
            tags=["task"],
        )
    )
    result = await runtime.consolidate()
    assert result.promoted >= 1
    episodic = await runtime.store.list_kind(MemoryKind.EPISODIC)
    assert any("onboarding" in r.content.lower() for r in episodic)
    assert await runtime.store.list_kind(MemoryKind.TASK) == []
    await runtime.stop()


@pytest.mark.asyncio
async def test_observe_mirrors_environment_state_memory(tmp_path: Path) -> None:
    runtime = MemoryRuntime(tmp_path / "m", tmp_path / "w")
    await runtime.start()
    from emily.memory.models import WorldObservation

    await runtime.observe(
        WorldObservation(text="Fabrikam opened Seattle office", entities=["Fabrikam", "Seattle"])
    )
    hits = await runtime.search(
        MemoryQuery(text="Fabrikam Seattle", kinds=[MemoryKind.ENVIRONMENT_STATE], limit=5)
    )
    assert hits
    stats = await runtime.stats()
    assert stats["world_entities"] >= 2
    assert stats["world_facts"] >= 1
    await runtime.stop()


@pytest.mark.asyncio
async def test_persistence_roundtrip_world_and_memory(tmp_path: Path) -> None:
    root_m = tmp_path / "mem"
    root_w = tmp_path / "world"
    runtime = MemoryRuntime(root_m, root_w)
    await runtime.start()
    rec = await runtime.remember(
        "long lived semantic fact about EmilyOS",
        kind=MemoryKind.SEMANTIC,
        title="EmilyOS",
        importance=0.85,
    )
    from emily.memory.models import ObservedRelation, WorldObservation

    await runtime.observe(
        WorldObservation(
            text="EmilyOS runs on Windows",
            entities=["EmilyOS", "Windows"],
            relations=[
                ObservedRelation(subject="EmilyOS", predicate="runs_on", object="Windows")
            ],
        )
    )
    await runtime.stop()

    runtime2 = MemoryRuntime(root_m, root_w)
    await runtime2.start()
    loaded = await runtime2.get(rec.memory_id)
    assert "EmilyOS" in loaded.content
    assert runtime2.world.get_entity("Windows") is not None
    assert any(r.predicate == "runs_on" for r in runtime2.world.snapshot().relations)
    await runtime2.stop()
