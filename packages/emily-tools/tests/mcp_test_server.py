"""Minimal MCP stdio server used by Emily MCP live tests."""

from __future__ import annotations

import json
import sys


def _read() -> dict[str, object] | None:
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line)


def _write(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def main() -> int:
    while True:
        message = _read()
        if message is None:
            return 0
        method = str(message.get("method") or "")
        req_id = message.get("id")
        if method == "initialize":
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "emily-test-mcp", "version": "0.1.0"},
                    },
                }
            )
            continue
        if method == "notifications/initialized":
            continue
        if method == "tools/list":
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": [
                            {
                                "name": "ping",
                                "description": "Ping tool",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"ping": {"type": "string"}},
                                },
                            }
                        ]
                    },
                }
            )
            continue
        if method == "tools/call":
            params = message.get("params") or {}
            args = params.get("arguments") if isinstance(params, dict) else {}
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"pong:{args}"}],
                        "isError": False,
                    },
                }
            )
            continue
        if req_id is not None:
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"unknown method {method}"},
                }
            )


if __name__ == "__main__":
    raise SystemExit(main())
