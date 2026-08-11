# Emily OS — Milestone Roadmap

Milestones are additive. Each must compile, run, test, and document without breaking prior milestones.

| ID | Name | Outcome |
|----|------|---------|
| **M0** | Platform Spine | Monorepo, core contracts, event bus, config, observability ports, bootable kernel, CLI |
| **M1** | Provider Fabric | NVIDIA NIM + RoutesMe adapters, router, health, failover, cost/latency metadata |
| **M2** | Mission Runtime | Mission/objective/task model, LangGraph backbone, checkpointing, pause/resume |
| **M3** | Agent Runtime | Dynamic agent spawn/destroy, role registry, supervision, verification loop |
| **M4** | Memory & World Model | Multi-memory systems, retrieval orchestration, continuous world model |
| **M5** | Tool & MCP Runtime | Tool metadata/permissions, MCP discovery, hot reload, capability isolation |
| **M6** | Desktop Runtime | Windows a11y, window/clipboard/input, PowerShell, registry (policy-gated) |
| **M7** | Browser Runtime | Playwright + CDP, profiles, session persistence, DOM grounding |
| **M8** | Vision & Voice | Screen/OCR/GUI grounding; STT/TTS providers; VAD; wake word |
| **M9** | Security & Policy | Secrets vault, capability tokens, approval gates, audit log, sandboxes |
| **M10** | Observability Suite | OpenTelemetry export, replay, cost/latency analytics dashboards |
| **M11** | Plugin SDK | Hot install/reload, versioning, marketplace packaging |
| **M12** | Desktop UI | React + TypeScript + Tauri: missions, agents, memory, workflows, terminal |
| **M13** | Coding Workbench | Repo indexing, git, diffs, live execution, review agents |
| **M14** | Trading Module | Broker adapters, paper trading, risk limits, human approval (optional) |

## Milestone 0 Acceptance Criteria

1. Editable install of all M0 packages succeeds on Windows + Python 3.12+.
2. `emily version` and `emily health` succeed.
3. Kernel boots, publishes lifecycle events, shuts down cleanly.
4. In-process async event bus delivers typed envelopes with middleware.
5. Config loads from environment / `.env` with Pydantic v2 validation.
6. Unit tests cover core IDs, events, config, kernel lifecycle.
7. `ruff`, `black --check`, and `mypy` pass on M0 packages.
8. Architecture docs exist under `docs/architecture/`.
