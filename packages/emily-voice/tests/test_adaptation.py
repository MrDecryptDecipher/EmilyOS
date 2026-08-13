"""User adaptation observe + apply tests."""

from __future__ import annotations

from pathlib import Path

from emily.voice.adaptation import UserAdaptation, load_adaptation, save_adaptation
from emily.voice.personality import DEFAULT_PERSONALITY


def test_observe_and_apply(tmp_path: Path) -> None:
    path = tmp_path / "adaptation.json"
    adapt = UserAdaptation(path=path)
    adapt.observe_user_turn("Hey yeah that sounds cool yaar")
    adapt.observe_reply("Sure, on it.")
    adapt.observe_interrupt()
    assert adapt.profile.turn_count == 1
    assert adapt.profile.interrupt_count == 1
    assert adapt.profile.formal_casual > 0.5
    adjusted = adapt.apply_to_personality(DEFAULT_PERSONALITY)
    assert adjusted.speaking_rate != DEFAULT_PERSONALITY.speaking_rate or adjusted.formality != DEFAULT_PERSONALITY.formality
    loaded = load_adaptation(path)
    assert loaded.turn_count == 1
    save_adaptation(loaded, path)
    assert path.exists()
