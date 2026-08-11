# Milestone 0 — Platform Spine (complete)

## Design decisions

1. **Monorepo with package boundaries** — each bounded context is an installable package under `packages/`, not a flat `app/` module dump.
2. **Protocols in `emily-core`** — adapters depend inward; no circular imports across runtimes.
3. **Event bus as the cross-cutting fabric** — subsystems communicate via typed envelopes, not direct calls.
4. **Config accepts legacy and `EMILY_` env keys** — existing `.env` keeps working while new installs use the prefixed template.
5. **Kernel owns lifecycle only** — no reasoning, no tools, no providers in M0.
6. **Python 3.12+** — platform target; local venv recreated on 3.12.10.

## Acceptance (verified)

| Criterion | Status |
|-----------|--------|
| Editable install | Pass |
| `emily version` / `emily health` / `emily boot` | Pass |
| Kernel lifecycle events | Pass |
| Async event bus + middleware | Pass |
| Pydantic v2 config | Pass |
| Unit + integration tests | 17 passed, ~89% coverage |
| ruff / black / mypy | Pass |

## Next

**Milestone 1 — Provider Fabric**: NVIDIA NIM + RoutesMe adapters, provider router, health probes, failover, cost/latency metadata.
