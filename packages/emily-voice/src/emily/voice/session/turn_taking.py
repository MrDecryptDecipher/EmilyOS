"""Turn-taking helpers."""

from __future__ import annotations

from emily.voice.models import VoiceTurnState
from emily.voice.session.state import TurnStateMachine


class TurnTakingController:
    def __init__(self) -> None:
        self.machine = TurnStateMachine()

    @property
    def state(self) -> VoiceTurnState:
        return self.machine.state

    def begin_listen(self) -> None:
        self.machine.transition(VoiceTurnState.LISTENING)

    def begin_process(self) -> None:
        if self.state == VoiceTurnState.IDLE:
            self.machine.transition(VoiceTurnState.PROCESSING)
        elif self.state == VoiceTurnState.LISTENING:
            self.machine.transition(VoiceTurnState.PROCESSING)
        else:
            self.machine.transition(VoiceTurnState.PROCESSING)

    def begin_think(self) -> None:
        if self.state == VoiceTurnState.IDLE:
            self.machine.transition(VoiceTurnState.THINKING)
        else:
            self.machine.transition(VoiceTurnState.THINKING)

    def begin_speak(self) -> None:
        if self.state == VoiceTurnState.IDLE:
            self.machine.transition(VoiceTurnState.SPEAKING)
        else:
            self.machine.transition(VoiceTurnState.SPEAKING)

    def interrupt(self) -> None:
        self.machine.transition(VoiceTurnState.INTERRUPTED)

    def idle(self) -> None:
        if self.state != VoiceTurnState.IDLE:
            self.machine.transition(VoiceTurnState.IDLE)

    def error(self) -> None:
        self.machine.force(VoiceTurnState.ERROR)
