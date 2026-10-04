# Milestone 3 — Agent Runtime

## Design decisions

1. **Agents are ephemeral workers** — spawned for work, supervised, then destroyed; not long-lived chat personas.
2. **Role registry is declarative** — each `AgentKind` maps to capabilities, retries, and output style (13+ built-ins).
3. **Supervisor owns lifecycle** — spawn / assign / await / terminate with status tracking, pool gating, and events.
4. **Verification loop is first-class** — work → verify → critique feedback → capped retries; structured `VerificationDecision`.
5. **Specialized offline workers** — research/coding/document/data/security/monitoring/… produce kind-shaped artifacts without live LLMs.
6. **Optional LLM workers** — `EMILY_AGENT_LLM_WORKERS=true` uses provider router with timeout + heuristic fallback.
7. **Teams** — sequential pipelines with handoff + concurrent fan-out.
8. **Mission integration via TaskExecutor port** — mission graph execute node delegates to agents when available.
9. **Analytics + history** — in-process run metrics and optional `data/agents/` JSON history.

## Package

`packages/emily-agents` → `emily.agents`

## CLI

- `emily agent roles|list|run|pipeline|stats|history`

## Acceptance criteria

1. Spawn and terminate agents dynamically by kind.
2. Role registry lists built-in kinds with capabilities.
3. Supervisor runs a task through work + verification with critique retry.
4. Mission execute path can delegate to AgentTaskExecutor.
5. Pipeline / fan-out team orchestration works.
6. Pool capacity limits concurrent runs.
7. Kernel subsystem + CLI work.
8. Offline tests + smoke harness pass; ruff/black/mypy clean.
