# Emily OS — Executive Kernel

## Responsibility

The Executive Kernel is the process control plane. It does **not** reason about user goals. It:

1. Loads and validates configuration
2. Initializes observability
3. Creates the event bus
4. Registers subsystem lifecycles
5. Emits bootstrap / shutdown events
6. Owns orderly start and stop ordering

## Lifecycle States

```
CREATED → INITIALIZING → RUNNING → DRAINING → STOPPED
                      ↘ FAILED
```

## Subsystem Protocol

Every runtime (providers, memory, tools, …) implements `Subsystem`:

- `name: str`
- `startup_priority: int` (lower starts first)
- `shutdown_priority: int` (lower stops first)
- `async start(ctx: KernelContext) -> None`
- `async stop(ctx: KernelContext) -> None`
- `async health() -> HealthStatus`

M0 ships with a `NullSubsystem` and the observability/event infrastructure itself registered as subsystems.
