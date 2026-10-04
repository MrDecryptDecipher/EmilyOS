# Milestone 2 — Mission Runtime

## Design decisions

1. **Mission is the unit of work** — every user request becomes a Mission with Objectives → Tasks → execution graph → verification → reflection → archive.
2. **LangGraph is the orchestration backbone** — durable state, checkpointing, conditional routing, interruptible control flow.
3. **Control plane is explicit** — pause / resume / cancel are first-class operations applied at node boundaries via control signals + checkpoints.
4. **Persistence is dual-layer** — LangGraph checkpointer for graph state; MissionStore for domain archive/query.
5. **Planner is swappable** — heuristic planner for deterministic tests; LLM planner when provider router is available.
6. **No agent spawn yet** — M3 owns dynamic agents; M2 executes task nodes directly (reason via provider when present).

## Package

`packages/emily-missions` → `emily.missions`

## Dependencies

- `emily-core`, `emily-config`, `emily-events`, `emily-observability`, `emily-kernel`, `emily-providers`
- `langgraph>=1.2`
- `pydantic` v2

## Acceptance criteria

1. Create / plan / run a mission end-to-end (offline heuristic path).
2. Checkpoint after each major node; resume from pause.
3. Cancel a running mission cleanly.
4. Mission archive queryable via store + CLI.
5. Kernel subsystem boots with missions registered.
6. Unit/integration tests pass without live LLM; ruff/black/mypy clean.
