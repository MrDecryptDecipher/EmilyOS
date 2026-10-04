# emily-desktop

Real Windows desktop runtime for Emily OS — Win32 window control, clipboard, SendInput, PowerShell, and winreg.

There is **no simulated/mock backend**. Emily requires Windows and `EMILY_DESKTOP_LIVE=true`.

## Capabilities

- Enumerate / focus top-level windows (`EnumWindows`, `SetForegroundWindow`)
- Clipboard get/set (Win32 clipboard APIs)
- Keyboard / mouse synthesis (`SendInput`)
- PowerShell execution (`powershell.exe`)
- Registry get/set under allowlisted `HKCU\Software\EmilyOS` roots (`winreg`)

## Policy

- `EMILY_DESKTOP_CONTROL` required for all actions
- PowerShell: `allow_terminal` / `allow_system_commands` / `EMILY_DESKTOP_POWERSHELL`
- Registry writes: `allow_system_commands` / `EMILY_DESKTOP_REGISTRY_WRITE`

## CLI

```powershell
emily desktop status
emily desktop windows
emily desktop focus --title Notepad
emily desktop clipboard --set "hello"
emily desktop type "hello"
emily desktop powershell "Get-Date"
emily desktop registry "HKCU\Software\EmilyOS\Config" Version --set "0.1.0"
```
