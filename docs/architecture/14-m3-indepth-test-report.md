# M3 In-Depth Test Report

## Automated (offline)

| Suite | Result |
|-------|--------|
| Full offline pytest (`--ignore=tests/live`) | **Pass** |
| Coverage | **~90%** |
| Agent package focus | specialized workers, critique retry, pool, pipeline/fan-out, analytics/history, LLM fallback |
| Integration | kernel + providers + missions + agents e2e |

## Smoke harness

`python scripts/smoke_m3_agents.py`

| Probe | Result |
|-------|--------|
| Specialized kinds | Pass (6/6) |
| Critique retry | Pass |
| Pipeline + fan-out | Pass |
| Pool capacity | Pass |
| Events / analytics / history | Pass |
| Mission e2e via agents | Pass |
| Concurrent missions | Pass |

**7 / 7 passed**

## Coverage added in this pass

- Specialized kind-shaped workers (research/coding/document/data/security/monitoring/…)
- Word-boundary role inference (fixed `checkout` → false `verification` match)
- Critique-aware verification retries + structured `VerificationDecision`
- Agent pool concurrency gate + capacity errors
- Team pipeline handoff + fan-out + goal pipeline
- Analytics accumulator + file-backed run history
- Optional LLM worker with heuristic fallback
- Events: `agent.started`, `agent.retry`, `agent.verified`
- CLI: `pipeline`, `stats`, `history`
- Deep unit + integration e2e suites

## Bugs found (and fixed)

1. **HealthStatus nesting** — nested dicts in `details` violated scalar-only schema; flattened to scalars.
2. **Role inference substring trap** — `checkout` matched `check` → verification; switched to token/word matching.
3. **Verification-as-work false ACCEPT** — nested verify accepted REJECT text; single-pass path for verification work agents.
4. **Empty prior_output fallback** — empty string fell through to title and falsely ACCEPTed; honor explicit empty prior.

## Go / No-Go for M4

**Go for Milestone 4 — Memory & World Model.**
