"""Lexical retrieval over memory records."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime

from emily.core.types.memory import MemoryKind
from emily.memory.models import MemoryQuery, MemoryRecord, RetrievalHit
from emily.memory.store import MemoryStore

_TOKEN_RE = re.compile(r"[a-z0-9_]{2,}")


def tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


class LexicalRetriever:
    """Rank memories by token overlap, importance, and recency."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    async def search(self, query: MemoryQuery) -> list[RetrievalHit]:
        kinds = query.kinds or list(MemoryKind)
        candidates: list[MemoryRecord] = []
        for kind in kinds:
            candidates.extend(await self.store.list_kind(kind, limit=500))

        q_tokens = tokenize(query.text)
        if query.tags:
            tag_set = {t.lower() for t in query.tags}
        else:
            tag_set = set()

        now = datetime.now(UTC)
        hits: list[RetrievalHit] = []
        for record in candidates:
            if query.mission_id and record.mission_id and record.mission_id != query.mission_id:
                continue
            if tag_set and not tag_set.intersection({t.lower() for t in record.tags}):
                continue

            score, reasons = _score(record, q_tokens, now)
            if score < query.min_score:
                continue
            hits.append(RetrievalHit(record=record, score=score, reasons=reasons))

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[: query.limit]


def _score(
    record: MemoryRecord,
    q_tokens: set[str],
    now: datetime,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    blob = f"{record.title} {record.content} {' '.join(record.tags)}"
    doc_tokens = tokenize(blob)
    if not q_tokens:
        overlap = 0.0
    else:
        shared = q_tokens.intersection(doc_tokens)
        overlap = len(shared) / max(1, len(q_tokens))
        if shared:
            reasons.append(f"tokens:{','.join(sorted(shared)[:5])}")

    importance = record.importance
    if importance >= 0.7:
        reasons.append("high_importance")

    age_hours = max(0.0, (now - record.updated_at).total_seconds() / 3600.0)
    recency = 1.0 / (1.0 + math.log1p(age_hours))
    if age_hours < 24:
        reasons.append("recent")

    # Weighted blend in [0, 1]
    score = (0.55 * overlap) + (0.25 * importance) + (0.20 * recency)
    # Soft boost when title contains a query token
    title_tokens = tokenize(record.title)
    if q_tokens and q_tokens.intersection(title_tokens):
        score = min(1.0, score + 0.08)
        reasons.append("title_match")
    return round(score, 4), reasons
