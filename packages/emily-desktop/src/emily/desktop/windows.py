"""Real Windows desktop adapters (Win32 + winreg + PowerShell)."""

from __future__ import annotations

import asyncio
import ctypes
import sys
import time
from ctypes import wintypes
from datetime import UTC, datetime
from pathlib import Path

from emily.desktop.errors import DesktopError, DesktopNotFoundError
from emily.desktop.models import (
    ClipboardContent,
    DesktopWindow,
    InputEvent,
    PowerShellResult,
    RegistryValue,
)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

ENUMWINDOWS_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.OpenDesktopW.restype = wintypes.HANDLE
user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
user32.SetThreadDesktop.restype = wintypes.BOOL
user32.EnumDesktopWindows.argtypes = [wintypes.HANDLE, ENUMWINDOWS_PROC, wintypes.LPARAM]
user32.EnumDesktopWindows.restype = wintypes.BOOL

user32.EnumWindows.argtypes = [ENUMWINDOWS_PROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

psapi.GetModuleFileNameExW.argtypes = [
    wintypes.HANDLE,
    wintypes.HMODULE,
    wintypes.LPWSTR,
    wintypes.DWORD,
]
psapi.GetModuleFileNameExW.restype = wintypes.DWORD

SW_RESTORE = 9
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040


class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class InputUnion(ctypes.Union):
    _fields_ = [("mi", MouseInput), ("ki", KeyBdInput), ("hi", HardwareInput)]  # noqa: RUF012


class Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", InputUnion)]


def _require_win32() -> None:
    if sys.platform != "win32":
        raise DesktopError("desktop runtime requires Windows")


def _hwnd_to_id(hwnd: int) -> str:
    return f"hwnd:{hwnd}"


def _id_to_hwnd(window_id: str) -> int:
    if not window_id.startswith("hwnd:"):
        raise DesktopNotFoundError(f"invalid window id: {window_id}")
    try:
        return int(window_id.split(":", 1)[1])
    except ValueError as exc:
        raise DesktopNotFoundError(f"invalid window id: {window_id}") from exc


def _process_name(pid: int) -> str:
    access = PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ
    handle = kernel32.OpenProcess(access, False, pid)
    if not handle:
        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        if psapi.GetModuleFileNameExW(handle, None, buf, len(buf)):
            return Path(buf.value).name
        return ""
    finally:
        kernel32.CloseHandle(handle)


def _window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _window_bounds(hwnd: int) -> dict[str, int]:
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return {}
    return {
        "x": int(rect.left),
        "y": int(rect.top),
        "w": int(rect.right - rect.left),
        "h": int(rect.bottom - rect.top),
    }


def _enumerate_windows() -> list[DesktopWindow]:
    # Ensure current thread is attached to the interactive Default desktop
    h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
    if h_desk:
        user32.SetThreadDesktop(h_desk)

    foreground = int(user32.GetForegroundWindow() or 0)
    found: list[DesktopWindow] = []

    def _callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _window_title(hwnd)
        if not title.strip():
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        found.append(
            DesktopWindow(
                window_id=_hwnd_to_id(int(hwnd)),
                title=title,
                process_name=_process_name(int(pid.value)),
                pid=int(pid.value),
                focused=int(hwnd) == foreground,
                bounds=_window_bounds(int(hwnd)),
            )
        )
        return True

    success = False
    if h_desk:
        success = user32.EnumDesktopWindows(h_desk, ENUMWINDOWS_PROC(_callback), 0)
    if not success or not found:
        user32.EnumWindows(ENUMWINDOWS_PROC(_callback), 0)

    if not found:
        # Fallback for background service / multi-session Windows environments:
        # Query active interactive console session windows
        try:
            import csv
            import io
            import subprocess

            out = subprocess.check_output(
                ["tasklist", "/fi", "SESSION eq 1", "/v", "/fo", "csv"],
                timeout=4,
                stderr=subprocess.DEVNULL,
            ).decode("utf-8", errors="ignore")
            reader = csv.DictReader(io.StringIO(out))
            ignore_titles = {
                "N/A",
                "",
                "OleMainThreadWndName",
                "DWM Notification Window",
                "Temp Window",
                "Hidden Window",
                "Task Host Window",
                "Search",
                "Start",
            }
            for row in reader:
                title = (row.get("Window Title") or "").strip()
                pname = (row.get("Image Name") or "").strip()
                pid_str = (row.get("PID") or "0").strip()
                if title and title not in ignore_titles:
                    try:
                        pid = int(pid_str)
                    except ValueError:
                        pid = 0
                    found.append(
                        DesktopWindow(
                            window_id=f"pid:{pid}",
                            title=title,
                            process_name=pname,
                            pid=pid,
                            focused=False,
                            bounds={"x": 0, "y": 0, "width": 1920, "height": 1080},
                        )
                    )
        except Exception:
            pass

    return sorted(found, key=lambda w: w.title.lower())


def _focus_hwnd(hwnd: int) -> None:
    target_tid = user32.GetWindowThreadProcessId(hwnd, None)
    foreground = user32.GetForegroundWindow()
    foreground_tid = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
    current_tid = kernel32.GetCurrentThreadId()
    attached_fg = False
    attached_cur = False
    try:
        if foreground_tid and foreground_tid != current_tid:
            attached_fg = bool(user32.AttachThreadInput(current_tid, foreground_tid, True))
        if target_tid and target_tid != current_tid:
            attached_cur = bool(user32.AttachThreadInput(current_tid, target_tid, True))
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.BringWindowToTop(hwnd)
        if not user32.SetForegroundWindow(hwnd):
            raise DesktopError(
                "SetForegroundWindow failed",
                details={"hwnd": hwnd, "winerror": ctypes.get_last_error()},
            )
        foreground = int(user32.GetForegroundWindow() or 0)
        if foreground != hwnd:
            raise DesktopError(
                "window focus was not acquired",
                details={"hwnd": hwnd, "foreground": foreground},
            )
    finally:
        if attached_cur and target_tid:
            user32.AttachThreadInput(current_tid, target_tid, False)
        if attached_fg and foreground_tid:
            user32.AttachThreadInput(current_tid, foreground_tid, False)


def _clipboard_get_text() -> str:
    last_error = 0
    for _ in range(20):
        if user32.OpenClipboard(None):
            try:
                handle = user32.GetClipboardData(CF_UNICODETEXT)
                if not handle:
                    return ""
                pointer = kernel32.GlobalLock(handle)
                if not pointer:
                    return ""
                try:
                    return ctypes.wstring_at(pointer)
                finally:
                    kernel32.GlobalUnlock(handle)
            finally:
                user32.CloseClipboard()
        last_error = ctypes.get_last_error()
        time.sleep(0.05)
    raise OSError(f"OpenClipboard failed: {last_error}")


def _clipboard_set_text(text: str) -> None:
    last_error = 0
    for _ in range(20):
        if user32.OpenClipboard(None):
            try:
                user32.EmptyClipboard()
                data = text.encode("utf-16-le") + b"\x00\x00"
                handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                if not handle:
                    raise OSError("GlobalAlloc failed")
                pointer = kernel32.GlobalLock(handle)
                if not pointer:
                    raise OSError("GlobalLock failed")
                try:
                    ctypes.memmove(pointer, data, len(data))
                finally:
                    kernel32.GlobalUnlock(handle)
                if not user32.SetClipboardData(CF_UNICODETEXT, handle):
                    raise OSError(f"SetClipboardData failed: {ctypes.get_last_error()}")
                return
            finally:
                user32.CloseClipboard()
        last_error = ctypes.get_last_error()
        time.sleep(0.05)
    raise OSError(f"OpenClipboard failed: {last_error}")


def _send_inputs(inputs: list[Input]) -> None:
    if not inputs:
        return
    array_type = Input * len(inputs)
    arr = array_type(*inputs)
    sent = user32.SendInput(len(inputs), ctypes.byref(arr), ctypes.sizeof(Input))
    if sent != len(inputs):
        raise DesktopError(
            "SendInput failed",
            details={"sent": int(sent), "expected": len(inputs), "winerror": ctypes.get_last_error()},
        )


def _type_text(text: str) -> None:
    inputs: list[Input] = []
    for char in text:
        down = Input(
            type=INPUT_KEYBOARD,
            union=InputUnion(ki=KeyBdInput(0, ord(char), KEYEVENTF_UNICODE, 0, 0)),
        )
        up = Input(
            type=INPUT_KEYBOARD,
            union=InputUnion(ki=KeyBdInput(0, ord(char), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)),
        )
        inputs.extend((down, up))
    _send_inputs(inputs)


def _click_at(x: int, y: int, *, button: str = "left") -> None:
    screen_w = user32.GetSystemMetrics(0) or 1
    screen_h = user32.GetSystemMetrics(1) or 1
    abs_x = int(x * 65535 / max(screen_w - 1, 1))
    abs_y = int(y * 65535 / max(screen_h - 1, 1))
    if button == "right":
        down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
    elif button == "middle":
        down_flag, up_flag = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
    else:
        down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
    move = Input(
        type=INPUT_MOUSE,
        union=InputUnion(
            mi=MouseInput(abs_x, abs_y, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, 0)
        ),
    )
    down = Input(type=INPUT_MOUSE, union=InputUnion(mi=MouseInput(0, 0, 0, down_flag, 0, 0)))
    up = Input(type=INPUT_MOUSE, union=InputUnion(mi=MouseInput(0, 0, 0, up_flag, 0, 0)))
    _send_inputs([move, down, up])


def _parse_registry_path(path: str) -> tuple[int, str]:
    import winreg

    normalized = path.replace("/", "\\").strip("\\")
    roots = {
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
        "HKCR": winreg.HKEY_CLASSES_ROOT,
        "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
        "HKU": winreg.HKEY_USERS,
        "HKEY_USERS": winreg.HKEY_USERS,
    }
    parts = normalized.split("\\", 1)
    root_name = parts[0].upper()
    if root_name not in roots or len(parts) < 2:
        raise DesktopError(f"invalid registry path: {path}")
    return roots[root_name], parts[1]


def _registry_get(path: str, name: str) -> RegistryValue:
    import winreg

    root, subkey = _parse_registry_path(path)
    try:
        with winreg.OpenKey(root, subkey) as key:
            value, value_type = winreg.QueryValueEx(key, name)
    except FileNotFoundError as exc:
        raise DesktopNotFoundError(f"registry value not found: {path}\\{name}") from exc
    type_name = {
        winreg.REG_SZ: "string",
        winreg.REG_EXPAND_SZ: "expand_string",
        winreg.REG_DWORD: "dword",
        winreg.REG_QWORD: "qword",
        winreg.REG_BINARY: "binary",
        winreg.REG_MULTI_SZ: "multi_string",
    }.get(value_type, str(value_type))
    if isinstance(value, list):
        coerced: str | int | bool | None = "\n".join(str(v) for v in value)
    elif isinstance(value, bytes):
        coerced = value.hex()
    elif isinstance(value, (str, int, bool)):
        coerced = value
    else:
        coerced = str(value)
    return RegistryValue(path=path.replace("/", "\\"), name=name, value=coerced, value_type=type_name)


def _registry_set(path: str, name: str, value: str | int | bool) -> RegistryValue:
    import winreg

    root, subkey = _parse_registry_path(path)
    with winreg.CreateKeyEx(root, subkey) as key:
        if isinstance(value, bool):
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, 1 if value else 0)
            stored: str | int | bool = value
            value_type = "dword"
        elif isinstance(value, int):
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
            stored = value
            value_type = "dword"
        else:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(value))
            stored = str(value)
            value_type = "string"
    return RegistryValue(path=path.replace("/", "\\"), name=name, value=stored, value_type=value_type)


class WindowsDesktopBackend:
    """Production Windows desktop backend — no simulation."""

    name = "windows"

    def __init__(self) -> None:
        _require_win32()
        self._inputs: list[InputEvent] = []

    async def list_windows(self) -> list[DesktopWindow]:
        return await asyncio.to_thread(_enumerate_windows)

    async def focus_window(
        self, window_id: str | None = None, *, title: str | None = None
    ) -> DesktopWindow:
        windows = await self.list_windows()
        target: DesktopWindow | None = None
        if window_id:
            for window in windows:
                if window.window_id == window_id:
                    target = window
                    break
        elif title:
            needle = title.lower()
            for window in windows:
                if needle in window.title.lower():
                    target = window
                    break
        if target is None:
            raise DesktopNotFoundError("window not found")
        hwnd = _id_to_hwnd(target.window_id)
        await asyncio.to_thread(_focus_hwnd, hwnd)
        refreshed = await self.list_windows()
        for window in refreshed:
            if window.window_id == target.window_id:
                return window
        return target.model_copy(update={"focused": True})

    async def clipboard_get(self) -> ClipboardContent:
        try:
            text = await asyncio.to_thread(_clipboard_get_text)
        except Exception as exc:
            raise DesktopError("clipboard get failed", cause=exc) from exc
        return ClipboardContent(text=text, updated_at=datetime.now(UTC))

    async def clipboard_set(self, text: str) -> ClipboardContent:
        try:
            await asyncio.to_thread(_clipboard_set_text, text)
        except Exception as exc:
            raise DesktopError("clipboard set failed", cause=exc) from exc
        return ClipboardContent(text=text, updated_at=datetime.now(UTC))

    async def type_text(self, text: str) -> InputEvent:
        await asyncio.to_thread(_type_text, text)
        event = InputEvent(kind="type", payload={"text": text, "mode": "sendinput"})
        self._inputs.append(event)
        return event

    async def click(self, x: int, y: int, *, button: str = "left") -> InputEvent:
        await asyncio.to_thread(_click_at, x, y, button=button)
        event = InputEvent(
            kind="click",
            payload={"x": x, "y": y, "button": button, "mode": "sendinput"},
        )
        self._inputs.append(event)
        return event

    async def powershell(
        self,
        command: str,
        *,
        timeout_seconds: float = 15.0,
        dry_run: bool = False,
    ) -> PowerShellResult:
        if dry_run:
            return PowerShellResult(
                command=command,
                exit_code=0,
                stdout="",
                dry_run=True,
            )
        started = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
            return PowerShellResult(
                command=command,
                exit_code=int(proc.returncode or 0),
                stdout=stdout_b.decode("utf-8", errors="replace"),
                stderr=stderr_b.decode("utf-8", errors="replace"),
                dry_run=False,
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
            )
        except TimeoutError as exc:
            raise DesktopError(f"powershell timed out after {timeout_seconds}s") from exc

    async def registry_get(self, path: str, name: str) -> RegistryValue:
        try:
            return await asyncio.to_thread(_registry_get, path, name)
        except DesktopNotFoundError:
            raise
        except Exception as exc:
            raise DesktopError("registry get failed", cause=exc) from exc

    async def registry_set(self, path: str, name: str, value: str | int | bool) -> RegistryValue:
        try:
            return await asyncio.to_thread(_registry_set, path, name, value)
        except Exception as exc:
            raise DesktopError("registry set failed", cause=exc) from exc

    def input_log(self) -> list[InputEvent]:
        return list(self._inputs)


def create_backend(*, live: bool = True) -> WindowsDesktopBackend:
    """Create the production Windows backend.

    Simulation is not supported. ``live`` must be true.
    """
    if not live:
        raise DesktopError("simulated desktop backend is not supported; set EMILY_DESKTOP_LIVE=true")
    _require_win32()
    return WindowsDesktopBackend()


__all__ = ["WindowsDesktopBackend", "create_backend"]
