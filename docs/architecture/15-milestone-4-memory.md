# Milestone 4 — Memory & World Model

## Design decisions

1. **Multi-memory by kind** — working, task, conversation, episodic, semantic, preferences, failure/mission history, etc. map to `MemoryKind`.
2. **Offline-first retrieval** — lexical token overlap + importance + recency; optional vector/embeddings deferred (provider-backed later).
3. **File-backed durability** — JSON records under `data/memory/{kind}/`; world graph under `data/world/`.
4. **Continuous world model** — entities, relations, and facts updated via `observe()` and event subscriptions (missions/agents).
5. **Consolidation** — promote ephemeral working/task memories into long-term / episodic stores.
6. **Hexagonal facade** — `MemoryRuntime` is the port; subsystem wires kernel + CLI; missions/agents stay decoupled via events.

## Package

`packages/emily-memory` → `emily.memory`

## CLI

- `emily memory put|get|search|stats|consolidate|kinds`
- `emily world show|observe|entities`

## Acceptance criteria

1. Write / read / delete memory records by kind.
2. Cross-kind retrieval returns ranked hits.
3. World model accepts observations and exposes entities/relations/snapshot.
4. Consolidation promotes working → long_term/episodic.
5. Kernel subsystem + event hooks + CLI work.
6. Offline tests pass; ruff/mypy clean.
