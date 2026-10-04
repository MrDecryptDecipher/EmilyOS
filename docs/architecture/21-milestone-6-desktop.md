# Milestone 6 — Desktop Runtime

## Design decisions

1. **Policy-first** — all desktop actions require `desktop_control`; PowerShell/registry need additional flags.
2. **Real Windows only** — Win32 + `winreg` + `powershell.exe`. No simulated/mock/fake backend.
3. **Live required** — `EMILY_DESKTOP_LIVE=true` (default). Setting it false fails closed.
4. **Capability isolation** — actions map to tool permission `DESKTOP` (+ `EXECUTE` for PowerShell, `PRIVILEGED` for registry writes).
5. **Tool registration** — desktop actions register into `ToolRuntime` when both subsystems are present.
6. **Audit events** — every action emits `desktop.*` events for observability.

## Package

`packages/emily-desktop` → `emily.desktop`

## CLI

- `emily desktop status|windows|focus|clipboard|type|powershell|registry`

## Acceptance criteria

1. List/focus real top-level windows.
2. Clipboard get/set via Win32.
3. Input type/click via `SendInput`.
4. PowerShell gated + timeout.
5. Registry read/write under allowlisted `HKCU` roots via `winreg`.
6. Kernel subsystem + CLI + Windows tests; ruff/mypy clean.

## Status

**Complete** — see [22-milestone-6-complete.md](22-milestone-6-complete.md).
