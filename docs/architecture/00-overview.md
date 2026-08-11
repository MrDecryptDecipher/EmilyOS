# Emily OS — Architecture Overview (Volume 0)

## What Emily OS Is

Emily OS is an **AI-native operating platform** for Windows 11 (primary), with Linux and macOS as future targets. It is not a chatbot shell. It is a multi-agent, event-driven, durable-execution system that plans, executes, reflects, and learns across desktop, browser, voice, vision, coding, and workflow domains.

## Architectural Style

| Principle | Application |
|-----------|-------------|
| Hexagonal / Ports & Adapters | Runtimes depend on protocols; providers/tools are adapters |
| Event-driven | All cross-module communication via typed event envelopes |
| Async-first | `asyncio` end-to-end; sync bridges only at OS boundaries |
| CQRS where beneficial | Mission command path vs query/read models (world model, analytics) |
| DDD-inspired boundaries | Packages map to bounded contexts, not layers of convenience |
| Plugin-first | Skills, tools, MCP servers, and agents load through registries |
| Provider-agnostic | LLM / STT / TTS / embeddings behind interchangeable ports |
| Security-first | Capability tokens, policy engine, human-in-the-loop gates |

## Cognitive Control Plane

```
Executive Kernel
  → Goal Manager → Mission Planner → Strategic / Tactical / Operational Planners
  → Execution Runtime → Reflection → Learning → Memory Consolidator
  → Knowledge Graph ← Observation / Telemetry / Policy / Security
  → Provider Router → Skill / Tool / Desktop / Browser / Voice / Vision
  → Workflow / Plugin / MCP Runtimes
```

Every user request becomes a **Mission** with objectives, tasks, an execution graph, verification, reflection, learning, and archival. Pause, resume, checkpoint, replay, cancel, and retry are first-class.

## Package Map (Monorepo)

| Package | Bounded Context |
|---------|-----------------|
| `emily-core` | Shared IDs, errors, domain types, protocol ports |
| `emily-events` | Event bus, envelopes, subscriptions, middleware |
| `emily-config` | Typed configuration, secrets binding, feature flags |
| `emily-observability` | Structured logging, metrics, tracing ports |
| `emily-kernel` | Process lifecycle, subsystem registry, bootstrap |
| `emily-cli` (app) | Operator CLI for health, version, bootstrap |

Later milestones add: missions, agents, providers, memory, tools, security, desktop, browser, vision, voice, MCP, plugins, UI.

## Non-Goals for Milestone 0

- No LLM calls yet
- No desktop/browser automation yet
- No LangGraph mission graphs yet
- No UI shell yet

Milestone 0 proves the **platform spine**: installable packages, typed contracts, event bus, config, observability ports, and a bootable kernel.
