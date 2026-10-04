"""In-process mission control signals."""

from __future__ import annotations

from emily.missions.models import ControlSignal


class ControlPlane:
    """Thread-safe enough for asyncio single-event-loop use."""

    def __init__(self) -> None:
        self._signals: dict[str, ControlSignal] = {}

    def set(self, mission_id: str, signal: ControlSignal) -> None:
        self._signals[mission_id] = signal

    def get(self, mission_id: str) -> ControlSignal:
        return self._signals.get(mission_id, ControlSignal.RUN)

    def clear(self, mission_id: str) -> None:
        self._signals.pop(mission_id, None)
