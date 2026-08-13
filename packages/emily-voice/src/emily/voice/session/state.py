"""Turn state machine."""

from __future__ import annotations

from emily.voice.errors import VoiceError
from emily.voice.models import VoiceTurnState

_ALLOWED: dict[VoiceTurnState, set[VoiceTurnState]] = {
    VoiceTurnState.IDLE: {
        VoiceTurnState.LISTENING,
        VoiceTurnState.THINKING,
        VoiceTurnState.SPEAKING,
        VoiceTurnState.PROCESSING,
        VoiceTurnState.ERROR,
    },
    VoiceTurnState.LISTENING: {
        VoiceTurnState.PROCESSING,
        VoiceTurnState.THINKING,
        VoiceTurnState.IDLE,
        VoiceTurnState.INTERRUPTED,
        VoiceTurnState.ERROR,
    },
    VoiceTurnState.PROCESSING: {
        VoiceTurnState.THINKING,
        VoiceTurnState.SPEAKING,
        VoiceTurnState.IDLE,
        VoiceTurnState.INTERRUPTED,
        VoiceTurnState.ERROR,
    },
    VoiceTurnState.THINKING: {
        VoiceTurnState.SPEAKING,
        VoiceTurnState.IDLE,
        VoiceTurnState.INTERRUPTED,
        VoiceTurnState.ERROR,
    },
    VoiceTurnState.SPEAKING: {
        VoiceTurnState.IDLE,
        VoiceTurnState.LISTENING,
        VoiceTurnState.INTERRUPTED,
        VoiceTurnState.ERROR,
    },
    VoiceTurnState.INTERRUPTED: {
        VoiceTurnState.IDLE,
        VoiceTurnState.LISTENING,
        VoiceTurnState.PROCESSING,
        VoiceTurnState.ERROR,
    },
    VoiceTurnState.ERROR: {
        VoiceTurnState.IDLE,
        VoiceTurnState.LISTENING,
    },
}


class TurnStateMachine:
    def __init__(self, initial: VoiceTurnState = VoiceTurnState.IDLE) -> None:
        self.state = initial

    def transition(self, new_state: VoiceTurnState) -> VoiceTurnState:
        if new_state == self.state:
            return self.state
        allowed = _ALLOWED.get(self.state, set())
        if new_state not in allowed:
            raise VoiceError(
                f"invalid voice state transition {self.state} -> {new_state}",
                details={"from": self.state.value, "to": new_state.value},
            )
        self.state = new_state
        return self.state

    def force(self, new_state: VoiceTurnState) -> VoiceTurnState:
        self.state = new_state
        return self.state

    def reset(self) -> None:
        self.state = VoiceTurnState.IDLE
