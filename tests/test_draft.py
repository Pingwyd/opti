"""Tests for local draft persistence."""

from __future__ import annotations

import json

import pytest

import config
import draft


@pytest.fixture
def isolated_draft(tmp_path, monkeypatch):
    draft_path = tmp_path / "draft.json"
    monkeypatch.setattr(draft, "DRAFT_PATH", draft_path)
    return draft_path


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    config.load_config()
    return config_path


def test_save_and_load_round_trip(isolated_draft, isolated_config):
    draft.save_draft("hello world")
    assert isolated_draft.exists()
    assert draft.load_draft() == "hello world"

    data = json.loads(isolated_draft.read_text(encoding="utf-8"))
    assert "saved_at" in data
    assert data["text"] == "hello world"


def test_save_skips_whitespace_only(isolated_draft, isolated_config):
    draft.save_draft("   \n\t  ")
    assert not isolated_draft.exists()
    assert draft.load_draft() is None


def test_clear_draft(isolated_draft, isolated_config):
    draft.save_draft("keep me")
    assert draft.load_draft() == "keep me"
    draft.clear_draft()
    assert not isolated_draft.exists()
    assert draft.load_draft() is None


def test_persist_draft_false_skips_save_and_load(isolated_draft, isolated_config):
    cfg = config.load_config()
    cfg["persist_draft"] = False
    config.save_config(cfg)

    draft.save_draft("should not persist")
    assert not isolated_draft.exists()
    assert draft.load_draft() is None
