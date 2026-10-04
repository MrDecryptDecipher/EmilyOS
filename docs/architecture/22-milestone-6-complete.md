# Milestone 6 — Desktop Runtime (complete)

## Delivered

- Package `packages/emily-desktop` (`emily.desktop`)
- **Real** `WindowsDesktopBackend` only (Win32 windows/clipboard/SendInput, PowerShell, winreg)
- No simulated/mock backend — `EMILY_DESKTOP_LIVE=false` fails closed
- `DesktopPolicy` gates (`desktop_control`, PowerShell, registry allowlists)
- `DesktopRuntime` + `DesktopSubsystem` (startup priority 29)
- Tool registration into `ToolRuntime` (`desktop.*` plugin tools)
- CLI: `emily desktop status|windows|focus|clipboard|type|powershell|registry`
- Events: `desktop.*`
- Windows unit + integration tests + `scripts/smoke_m6_desktop.py`

## Acceptance

| Criteria | Status |
|----------|--------|
| List/focus windows | Pass (Win32) |
| Clipboard get/set | Pass (Win32) |
| Input type/click | Pass (`SendInput`) |
| PowerShell gated | Pass (`powershell.exe`) |
| Registry allowlist | Pass (`winreg` / HKCU) |
| Kernel + CLI + Windows tests | Pass |

## Next

Milestone 7 — Browser Runtime
