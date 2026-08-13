"""Barge-in session helpers."""

from __future__ import annotations

from emily.voice.audio.interruption import InterruptionController
from emily.voice.metrics import VoiceMetrics
from emily.voice.models import VoiceTurnState
from emily.voice.session.turn_taking import TurnTakingController


class BargeInHandler:
    """Marks turn interrupted and stops playback/generation."""

    def __init__(
        self,
        turns: TurnTakingController,
        interruption: InterruptionController,
        metrics: VoiceMetrics | None = None,
    ) -> None:
        self.turns = turns
        self.interruption = interruption
        self.metrics = metrics

    async def trigger(self) -> None:
        await self.interruption.interrupt()
        if self.turns.state != VoiceTurnState.INTERRUPTED:
            try:
                self.turns.interrupt()
            except Exception:
                self.turns.machine.force(VoiceTurnState.INTERRUPTED)
        if self.metrics is not None:
            self.metrics.record_barge_in()
            self.metrics.log_event("voice.barge_in")
