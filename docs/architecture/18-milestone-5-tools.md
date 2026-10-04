# Milestone 5 — Tool & MCP Runtime

## Design decisions

1. **Tools are capability-gated** — each tool declares `ToolPermissionLevel`s; invocation requires policy + optional capability token intersection.
2. **Registry is the source of truth** — builtins and MCP-discovered tools register under stable names with metadata/version.
3. **Offline-first MCP** — discovery loads a JSON catalog (stdio/HTTP descriptors); live process transport deferred; stubs prove isolation + hot reload.
4. **Hot reload** — re-read MCP catalog and reconcile registry (add/update/remove MCP-sourced tools) without kernel restart.
5. **Executor owns invocation** — permission check → timeout → invoke → events (`tool.invoked` / `tool.denied` / `tool.failed`).
6. **Hexagonal** — `ToolPort` remains the protocol; adapters wrap builtins and MCP stubs.

## Package

`packages/emily-tools` → `emily.tools`

## CLI

- `emily tool list|invoke|info|permissions`
- `emily mcp list|reload|show`

## Acceptance criteria

1. Register and list tools with permissions metadata.
2. Invoke builtins with permission gating.
3. Capability context can further restrict invocations.
4. MCP catalog discovery + hot reload updates registry.
5. Kernel subsystem + CLI work.
6. Offline tests pass; ruff/mypy clean.
