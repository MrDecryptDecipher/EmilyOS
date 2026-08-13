"""TTS engine protocol."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Protocol, runtime_checkable

from emily.voice.models import AudioChunk, SpeechPlan, TTSCapability


@runtime_checkable
class TTSEngine(Protocol):
    name: str

    @property
    def capabilities(self) -> TTSCapability: ...

    def available(self) -> bool: ...

    async def load(self) -> None: ...

    async def unload(self) -> None: ...

    async def synthesize(self, plan: SpeechPlan) -> AudioChunk: ...

    async def synthesize_stream(
        self, plan: SpeechPlan
    ) -> AsyncIterator[AudioChunk]: ...


async def stream_or_chunk(engine: TTSEngine, plan: SpeechPlan) -> AsyncIterator[AudioChunk]:
    """Prefer streaming segments when the engine exposes synthesize_stream."""
    stream = getattr(engine, "synthesize_stream", None)
    if stream is not None and engine.capabilities.streaming:
        async for chunk in stream(plan):
            yield chunk
        return
    # Sentence-level fallback: synthesize whole plan once
    yield await engine.synthesize(plan)


def backends_available(engines: Sequence[TTSEngine]) -> list[str]:
    return [e.name for e in engines if e.available()]
