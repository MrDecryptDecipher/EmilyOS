# Emily OS

**AI-native desktop operating platform** for Windows 11 (primary), designed for multi-agent reasoning, durable missions, desktop/browser automation, MCP, and enterprise-grade observability.

This is **not** a chatbot wrapper. Emily OS is a modular, event-driven operating platform.

## Status

**Milestone 0 — Platform Spine** (current)

- Modular monorepo under `packages/` and `apps/`
- Core types, errors, and protocol ports
- Async in-process event bus
- Typed configuration (NVIDIA NIM + RoutesMe ready)
- Structured logging + metrics/tracer ports
- Bootable executive kernel + operator CLI

See [docs/architecture/02-milestones.md](docs/architecture/02-milestones.md) for the full roadmap.

## Requirements

- Windows 11 (primary)
- Python 3.12+
- Git

## Quick start

```powershell
cd C:\Users\FCI\Desktop\EMILY
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
.\scripts\install-dev.ps1
copy .env.example .env   # if you do not already have .env
emily version
emily health
emily boot
```

## Repository layout

| Path | Role |
|------|------|
| `packages/emily-core` | IDs, errors, domain enums, protocol ports |
| `packages/emily-events` | Event envelopes + async bus |
| `packages/emily-config` | Pydantic settings |
| `packages/emily-observability` | Logging / metrics / tracing adapters |
| `packages/emily-kernel` | Executive kernel lifecycle |
| `apps/emily-cli` | `emily` CLI |
| `docs/architecture` | Architecture notes |

## Providers (configured in M0, wired in M1)

| Role | Provider | Model |
|------|----------|-------|
| Primary | NVIDIA NIM | `z-ai/glm-5.2` |
| Secondary | RoutesMe (OpenAI-compatible) | `DeepSeek-V4-Flash-0731` |

## Development

```powershell
pytest
ruff check packages apps tests
black --check packages apps tests
mypy
```

## License

Apache-2.0 (see packaging metadata; full LICENSE file lands with M1 release packaging).
