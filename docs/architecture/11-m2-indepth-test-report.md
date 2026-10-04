# M2 In-Depth Test Report

## Automated (offline)

| Suite | Result |
|-------|--------|
| Full offline pytest (`--ignore=tests/live`) | **Pass** |
| Coverage | **~92%** |
| Mission package focus | graph paths, runtime state machine, store, planners, concurrency, events |
| Integration | kernel + providers + missions |

## Smoke harness

`python scripts/smoke_m2_missions.py`

| Probe | Result |
|-------|--------|
| Full run | Pass |
| Pause → resume | Pass |
| Cancel guard | Pass |
| Graph pause at plan | Pass |
| Lifecycle events | Pass |
| Concurrent missions | Pass |

**6 / 6 passed**

## Coverage added in this pass

- Graph: happy path events, execute pause, execute cancel, verify failure
- Runtime: start guards, resume guards, event emission, metadata/priority roundtrip, concurrency
- Planner: empty goal, LLM success/fallback/empty response, create_default flags
- Store: delete, ordering, overwrite timestamps
- Integration: providers + missions under one kernel

## Bugs found

None blocking. No production code defects required fixes in this pass.

## Go / No-Go for M3

**Go for Milestone 3 — Agent Runtime.**
