# Milestone 1 — Complete

## Delivered

- `packages/emily-providers` — OpenAI-compatible transport, NVIDIA + RoutesMe adapters
- `ProviderRouter` — primary/backup failover + analytics
- `ProvidersSubsystem` — kernel lifecycle integration
- CLI: `emily providers`, `emily chat`
- Config: timeout / retries / failover flags
- Events: `provider.health.changed`, `provider.invoked`, `provider.failover`
- Docs: `docs/architecture/06-milestone-1-providers.md`

## Verified

| Check | Result |
|-------|--------|
| Unit/integration tests | 25 passed (~85% coverage) |
| ruff / black / mypy | Pass |
| `emily providers` live | NVIDIA + RoutesMe `/models` healthy |
| Known-good NVIDIA chat (`deepseek-ai/deepseek-v4-flash-0731`) | Works |
| Configured primary `z-ai/glm-5.2` chat | Listed on NIM but currently hangs (read timeout) |
| RoutesMe chat | Intermittent HTTP 429 under load |

Failover on transport/5xx/invocation errors is implemented; when primary times out, backup is attempted automatically unless `--provider` forces a single vendor.

## Next

**Milestone 2 — Mission Runtime**: mission/objective/task model, LangGraph orchestration, checkpointing, pause/resume/cancel.
