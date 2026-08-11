"""Tests for emily-core identifiers and errors."""

from __future__ import annotations

import pytest

from emily.core.errors import ConfigError, EmilyError, ErrorCode
from emily.core.ids import new_event_id, new_id, new_mission_id


def test_new_id_format() -> None:
    value = new_id("evt")
    assert value.startswith("evt_")
    parts = value.split("_")
    assert len(parts) == 3


def test_new_id_rejects_bad_prefix() -> None:
    with pytest.raises(ValueError):
        new_id("bad prefix!")


def test_typed_id_helpers() -> None:
    assert str(new_event_id()).startswith("evt_")
    assert str(new_mission_id()).startswith("mis_")


def test_emily_error_to_dict() -> None:
    err = ConfigError("boom", details={"field": "x"})
    assert isinstance(err, EmilyError)
    payload = err.to_dict()
    assert payload["code"] == ErrorCode.CONFIG
    assert payload["message"] == "boom"
    assert payload["details"]["field"] == "x"
