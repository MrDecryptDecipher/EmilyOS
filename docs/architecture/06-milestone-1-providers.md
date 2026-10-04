# Milestone 1 — Provider Fabric

## Design decisions

1. **OpenAI-compatible transport shared** — NVIDIA NIM and RoutesMe both speak Chat Completions; one HTTP client, two thin adapters.
2. **Router owns failover** — callers depend on `LLMProviderPort` / `ProviderRouter`, never on a concrete vendor.
3. **Analytics at the fabric edge** — every completion records latency, token usage, estimated cost, and provider identity.
4. **Health is continuous** — adapters expose status; the providers subsystem publishes `provider.health.changed`.
5. **Secrets never leave config** — adapters receive `SecretStr` values; logs redact keys.
6. **Tests mock HTTP** — no live API calls in CI; optional live smoke via CLI.

## Package

`packages/emily-providers` → `emily.providers`

## Dependencies

- `emily-core`, `emily-config`, `emily-events`, `emily-observability`
- `httpx` (async HTTP)
- `pydantic` v2

## Acceptance criteria

1. NVIDIA + RoutesMe adapters complete and stream via OpenAI-compatible API.
2. Router selects primary, fails over to backup on provider errors.
3. Health aggregation available via kernel subsystem + `emily providers`.
4. Usage/latency/cost metadata recorded per call.
5. Unit tests pass without network; ruff/black/mypy clean.
6. `emily chat "ping"` works when API keys are present (manual/live).
