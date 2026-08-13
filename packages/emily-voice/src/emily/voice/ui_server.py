"""Minimal stdlib HTTP server exposing live voice status for desktop UI."""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse


class VoiceStatusServer:
    """Serve GET /voice/status JSON from a background thread (no extra deps)."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        status_provider: Any | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self._status_provider = status_provider
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def bind(self, status_provider: Any) -> None:
        self._status_provider = status_provider

    async def snapshot(self) -> dict[str, Any]:
        provider = self._status_provider
        if provider is None:
            return {"enabled": False, "state": "idle", "message": "voice runtime not bound"}
        if hasattr(provider, "status"):
            snap = await provider.status()
            return {
                "enabled": True,
                "state": getattr(getattr(snap, "state", None), "value", str(snap.state)),
                "backends": getattr(snap, "backends", {}),
                "metrics": (
                    snap.metrics.model_dump(mode="json")
                    if hasattr(snap.metrics, "model_dump")
                    else snap.metrics
                ),
                "hardware": (
                    snap.hardware.model_dump(mode="json")
                    if hasattr(snap.hardware, "model_dump")
                    else {}
                ),
            }
        if hasattr(provider, "stats"):
            return {"enabled": True, "stats": provider.stats()}
        return {"enabled": False, "state": "idle"}

    def start(self) -> None:
        if self._httpd is not None:
            return
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                return

            def do_GET(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path not in {"/voice/status", "/health"}:
                    self.send_response(404)
                    self.end_headers()
                    return
                try:
                    payload = asyncio.run(server.snapshot())
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    try:
                        payload = loop.run_until_complete(server.snapshot())
                    finally:
                        loop.close()
                if path == "/health":
                    payload = {"ok": True}
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True, name="voice-ui-http")
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        self._httpd = None
        self._thread = None
