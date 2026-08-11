# Emily OS — Monorepo Layout

```
EMILY/
├── apps/
│   └── emily-cli/                 # Operator CLI (Typer)
├── packages/
│   ├── emily-core/                # Types, errors, protocol ports
│   ├── emily-events/              # Event bus
│   ├── emily-config/              # Settings & feature flags
│   ├── emily-observability/       # Logging + telemetry ports
│   └── emily-kernel/              # Executive kernel bootstrap
├── docs/
│   └── architecture/
├── tests/
│   └── integration/
├── configs/                       # Non-secret default configs
├── data/                          # Local runtime data (gitignored content)
├── scripts/                       # Dev & CI helpers
├── pyproject.toml                 # Workspace root + tool config
├── README.md
└── .env.example
```

## Dependency Direction (acyclic)

```
emily-cli → emily-kernel → emily-events
                         → emily-config
                         → emily-observability
                         → emily-core

emily-events        → emily-core
emily-config        → emily-core
emily-observability → emily-core
emily-kernel        → emily-core + events + config + observability
```

No package may import a higher-level package. Cross-cutting concerns go through events or protocol ports defined in `emily-core`.

## Legacy `app/` Directory

The pre-M0 empty `app/` tree is **not** part of the installable platform. It remains only as a historical scaffold until M1 migrates any residual references. New code belongs under `packages/` and `apps/`.
