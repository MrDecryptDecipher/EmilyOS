"""Real MCP stdio JSON-RPC client (Model Context Protocol)."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any


class MCPClientError(RuntimeError):
    """Raised when an MCP server call fails."""


class StdioMCPClient:
    """Speaks MCP over stdio with a child process."""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        *,
        env: dict[str, str] | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.command = command
        self.args = list(args or [])
        self.env = env
        self.timeout_seconds = timeout_seconds
        self._proc: asyncio.subprocess.Process | None = None
        self._next_id = 1
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._proc is not None:
            return
        env = os.environ.copy()
        if self.env:
            env.update(self.env)
        self._proc = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        await self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "emily-os", "version": "0.1.0"},
            },
        )
        await self.notify("notifications/initialized", {})

    async def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        if proc.stdin and not proc.stdin.is_closing():
            proc.stdin.close()
        try:
            await asyncio.wait_for(proc.wait(), timeout=3.0)
        except TimeoutError:
            proc.kill()
            await proc.wait()

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self.request("tools/list", {})
        tools = result.get("tools") if isinstance(result, dict) else None
        if not isinstance(tools, list):
            return []
        return [t for t in tools if isinstance(t, dict)]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = await self.request(
            "tools/call",
            {"name": name, "arguments": dict(arguments or {})},
        )
        if not isinstance(result, dict):
            return {"content": result}
        return result

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params})

    async def request(self, method: str, params: dict[str, Any]) -> Any:
        async with self._lock:
            req_id = self._next_id
            self._next_id += 1
            await self._write({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
            while True:
                message = await self._read()
                if message.get("id") != req_id:
                    # Ignore unrelated notifications / stray messages.
                    continue
                if "error" in message:
                    err = message["error"]
                    raise MCPClientError(str(err))
                return message.get("result")

    async def _write(self, payload: dict[str, Any]) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise MCPClientError("MCP process is not running")
        data = (json.dumps(payload) + "\n").encode("utf-8")
        proc.stdin.write(data)
        await proc.stdin.drain()

    async def _read(self) -> dict[str, Any]:
        proc = self._proc
        if proc is None or proc.stdout is None:
            raise MCPClientError("MCP process is not running")
        try:
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=self.timeout_seconds)
        except TimeoutError as exc:
            raise MCPClientError(f"MCP read timed out after {self.timeout_seconds}s") from exc
        if not line:
            stderr = b""
            if proc.stderr is not None:
                stderr = await proc.stderr.read()
            raise MCPClientError(
                f"MCP server closed stdout: {stderr.decode('utf-8', errors='replace')}"
            )
        try:
            message = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise MCPClientError(f"invalid MCP JSON: {line!r}") from exc
        if not isinstance(message, dict):
            raise MCPClientError("MCP message must be an object")
        return message
