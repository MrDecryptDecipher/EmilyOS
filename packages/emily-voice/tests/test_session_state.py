"""Session turn state machine tests."""

from __future__ import annotations

import pytest

from emily.voice.errors import VoiceError
from emily.voice.models import VoiceTurnState
from emily.voice.session.state import TurnStateMachine
from emily.voice.session.turn_taking import TurnTakingController


def test_happy_path_transitions() -> None:
    turns = TurnTakingController()
    turns.begin_listen()
    assert turns.state == VoiceTurnState.LISTENING
    turns.begin_process()
    assert turns.state == VoiceTurnState.PROCESSING
    turns.begin_think()
    assert turns.state == VoiceTurnState.THINKING
    turns.begin_speak()
    assert turns.state == VoiceTurnState.SPEAKING
    turns.idle()
    assert turns.state == VoiceTurnState.IDLE


def test_barge_in_from_speaking() -> None:
    turns = TurnTakingController()
    turns.begin_speak()
    turns.interrupt()
    assert turns.state == VoiceTurnState.INTERRUPTED
    turns.idle()
    assert turns.state == VoiceTurnState.IDLE


def test_invalid_transition_raises() -> None:
    machine = TurnStateMachine(VoiceTurnState.ERROR)
    with pytest.raises(VoiceError):
        machine.transition(VoiceTurnState.SPEAKING)
