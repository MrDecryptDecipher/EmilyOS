"""Sentence streaming buffer tests."""

from __future__ import annotations

from emily.voice.session.conversation import buffer_sentences


def test_buffer_splits_on_period() -> None:
    completed, buf = buffer_sentences("Hello world. ", "")
    assert completed == ["Hello world."]
    assert buf == ""


def test_buffer_holds_incomplete() -> None:
    completed, buf = buffer_sentences("Hello", "")
    assert completed == []
    assert buf == "Hello"
    completed, buf = buffer_sentences(" there!", buf)
    assert completed == ["Hello there!"]
    assert buf == ""


def test_buffer_newline_and_length() -> None:
    completed, buf = buffer_sentences("line one\n", "")
    assert completed == ["line one"]
    long = "word " * 40
    completed, buf = buffer_sentences(long, "", length_threshold=50)
    assert len(completed) >= 1
    assert isinstance(buf, str)
