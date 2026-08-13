"""Voice UI HTTP server tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from emily.voice.models import VoiceTurnState
from emily.voice.ui_server import VoiceStatusServer


class _Provider:
    async def status(self):
        from emily.voice.models import VoiceStatus

        return VoiceStatus(
            enabled=True,
            started=True,
            state=VoiceTurnState.LISTENING,
            backends={"kokoro": True},
        )


@pytest.mark.asyncio
async def test_voice_status_snapshot() -> None:
    server = VoiceStatusServer(port=18765)
    server.bind(_Provider())
    snap = await server.snapshot()
    assert snap["enabled"] is True
    assert snap["state"] == "listening"
