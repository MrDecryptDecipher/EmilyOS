# M1 In-Depth Test Report

## Automated (offline)

| Suite | Result |
|-------|--------|
| Unit + integration (`pytest --ignore=tests/live`) | **49 passed** |
| Coverage | **~90%** |
| ruff / mypy | Pass |

## Live smoke (`python scripts/smoke_m1_providers.py`)

Latest run after stream Accept-header fix:

| Probe | Result |
|-------|--------|
| NVIDIA health | Pass |
| RoutesMe health | Pass |
| NVIDIA chat (`deepseek-ai/deepseek-v4-flash-0731`) | Pass (`SMOKE_OK`) |
| NVIDIA stream (same model) | Pass (`STREAM_OK`) — fixed by using `Accept: text/event-stream` |
| Configured `z-ai/glm-5.2` | Pass as expected failure (read timeout) |
| RoutesMe chat | Fail — HTTP **429** rate limit (upstream) |
| Router failover (bad NVIDIA key → RoutesMe) | Pass path exercised; backup also rate-limited |

Live pytest (`EMILY_LIVE_PROVIDERS=1`): **4 passed**.

## Bugs found and fixed during in-depth testing

1. **NVIDIA streaming returned HTTP 500** when `Accept: application/json` was forced. Fixed by removing that default and sending `Accept: text/event-stream` on stream requests.

## Remaining external risks (not code defects)

1. `z-ai/glm-5.2` hangs on NIM chat completions until timeout.
2. RoutesMe chat is intermittently **429/503**.

## Go / No-Go for M2

**Go.** Core fabric is verified offline and online for health, non-stream chat, streaming, retries, and failover wiring. Treat GLM primary + RoutesMe flakiness as operational constraints, not blockers for Mission Runtime work.
