# M4 In-Depth Test Report

## Automated (offline)

| Suite | Result |
|-------|--------|
| Full offline pytest (`--ignore=tests/live`) | **Pass** |
| Coverage | **~91%** |
| Memory package focus | store CRUD, concurrent writes, lexical ranking, consolidation, persistence |
| World model focus | entity upsert, relation dedupe, fact ingest, reload |
| Integration | kernel + providers + missions + agents + memory/world e2e |

## Smoke harness

`python scripts/smoke_m4_memory.py`

| Probe | Result |
|-------|--------|
| CRUD + search | Pass |
| World observe | Pass |
| Consolidate (working→long_term, task→episodic) | Pass |
| Events | Pass |
| Persistence roundtrip | Pass |
| Concurrency (10 parallel write/search) | Pass |
| Kernel event hooks (mission/agent → memory/world) | Pass |
| Mission history retrieval | Pass |

**8 / 8 passed**

## Coverage added in this pass

- Kind-scoped get/delete + concurrent store writes
- Retrieval ranking: title boost, tags, mission filter, min_score
- Task→episodic consolidation path
- World relation dedupe + confidence upsert + entity id lookup
- Memory disabled subsystem health path
- Full-stack kernel e2e (preferences + world seed + mission + agent + consolidate)
- Expanded smoke harness with persistence / concurrency / kernel hooks

## Bugs found (and fixed)

1. **Smoke consolidate truthiness trap** — `ok = … and long_term and episodic` returned a `list[MemoryRecord]` (last truthy `and` operand) instead of `bool`, breaking JSON reporting. Fixed to explicit `len(...) > 0` checks.

No production runtime defects required changes in this pass.

## Go / No-Go for M5

**Go for Milestone 5 — Tool & MCP Runtime.**
