"""ASR engine protocol."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from emily.voice.models import AudioChunk


@runtime_checkable
class ASREngine(Protocol):
    name: str

    def available(self) -> bool: ...

    async def load(self) -> None: ...

    async def unload(self) -> None: ...

    async def transcribe(self, audio: AudioChunk, *, language: str | None = None) -> str: ...

    async def transcribe_stream(
        self, audio: AudioChunk, *, language: str | None = None
    ) -> AsyncIterator[str]: ...
