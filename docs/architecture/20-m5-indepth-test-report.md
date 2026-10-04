# M5 In-Depth Test Report

## Automated (offline)

| Suite | Result |
|-------|--------|
| Full offline pytest (`--ignore=tests/live`) | **Pass** |
| Coverage | **~91%** (repo-wide) |
| Tools package focus | policy matrix, capability tokens, disabled tools, concurrent invoke, math edges |
| MCP focus | hot reload add/remove, disabled servers skipped, empty catalog, default idempotent |
| Integration | kernel + providers + memory + tools + missions + agents |

## Smoke harness

`python scripts/smoke_m5_tools.py`

| Probe | Result |
|-------|--------|
| Builtins | Pass |
| Capability isolation | Pass |
| Policy deny (network) | Pass |
| MCP hot reload | Pass |
| Events (invoked/denied/reloaded) | Pass |
| Concurrency (20 parallel) | Pass |
| Kernel stack | Pass |
| Disabled tool | Pass |

**8 / 8 passed**

## Coverage added in this pass

- Settings→permission matrix (read/write/execute/network/desktop/browser/privileged)
- Disabled tool denial + `ToolNotFoundError`
- Registry unregister / clear MCP source
- Concurrent builtin invokes
- Math edge cases (`//`, unary, empty expression)
- MCP disabled-server skip + empty catalog reload
- Full-stack kernel e2e with memory/missions/agents
- Tools-disabled health path
- Expanded smoke with policy/events/concurrency/kernel/disabled

## Bugs found

None blocking. No production code defects required fixes in this pass.

## Go / No-Go for M6

**Go for Milestone 6 — Desktop Runtime.**
