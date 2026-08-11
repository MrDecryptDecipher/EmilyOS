# Emily OS — Event Model

## Envelope

Every event is an immutable `EventEnvelope` with:

- `event_id` — ULID-ordered unique id
- `event_type` — dotted name (`kernel.started`, `mission.created`, …)
- `timestamp` — UTC aware datetime
- `source` — producing subsystem id
- `correlation_id` — request/mission correlation
- `causation_id` — parent event id
- `payload` — typed Pydantic model (serialized as JSON-compatible dict at the bus edge)
- `metadata` — optional headers (tenant, traceparent, capability scope)

## Bus Guarantees (M0 In-Process)

- Async publish/subscribe
- Topic / type prefix subscription
- Ordered delivery **per subscription** within a single process
- Middleware chain (logging, metrics hooks)
- Error isolation: handler failures do not stop other handlers
- Graceful drain on shutdown

M2+ will add durable outbox, cross-process transport, and replay.

## Naming Convention

```
{domain}.{entity}.{verb_past}

kernel.bootstrap.started
kernel.bootstrap.completed
kernel.shutdown.completed
config.reloaded
provider.health.changed
mission.created
agent.spawned
tool.invoked
policy.denied
```
