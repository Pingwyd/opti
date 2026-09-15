"""Tests for transform UI label helpers."""

from __future__ import annotations

from transform_ui import (
    action_label,
    chip_label,
    next_transform,
    placeholder_for,
    previous_transform,
    progress_verb,
)


def test_action_labels():
    assert action_label("optimize") == "Optimize"
    assert action_label("tone") == "Polish"
    assert action_label("extract") == "Extract"
    assert action_label("ask") == "Ask"


def test_chip_labels():
    assert chip_label("optimize") == "Optimize"
    assert chip_label("tone") == "Tone"
    assert chip_label("ask") == "Ask"


def test_transform_cycle():
    assert next_transform("optimize") == "tone"
    assert next_transform("extract") == "ask"
    assert next_transform("ask") == "optimize"
    assert previous_transform("optimize") == "ask"
    assert previous_transform("tone") == "optimize"


def test_placeholder_and_progress():
    assert "polish" in placeholder_for("tone").lower()
    assert "question" in placeholder_for("ask").lower()
    assert progress_verb("summarize") == "Summarizing"
    assert progress_verb("ask") == "Answering"
