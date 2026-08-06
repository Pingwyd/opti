"""Tests for local history storage and querying."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

import config
import history


@pytest.fixture
def isolated_history(tmp_path, monkeypatch):
    """Use a temp history.json so tests never touch real data."""
    history_path = tmp_path / "history.json"
    history_path.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(history, "HISTORY_PATH", history_path)
    return history_path


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    return config_path


def _seed_entries(path, count: int = 5) -> None:
    base = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
    entries = []
    for i in range(count):
        entries.append(
            {
                "id": f"id-{i}",
                "timestamp": (base + timedelta(days=i)).isoformat(),
                "input": f"prompt number {i} about cats",
                "output": f"optimized {i}",
                "model": "test-model",
                "tags": ["demo"] if i % 2 == 0 else [],
                "excluded_from_save": False,
            }
        )
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def test_query_entries_keyword_filter(isolated_history):
    _seed_entries(isolated_history, count=4)
    page, total = history.query_entries(keyword="cats", limit=10)
    assert total == 4
    assert len(page) == 4
    assert all("cats" in e["input"] for e in page)

    page, total = history.query_entries(keyword="number 2", limit=10)
    assert total == 1
    assert page[0]["input"] == "prompt number 2 about cats"


def test_query_entries_pagination(isolated_history):
    _seed_entries(isolated_history, count=7)
    page1, total = history.query_entries(offset=0, limit=3)
    page2, total2 = history.query_entries(offset=3, limit=3)
    page3, total3 = history.query_entries(offset=6, limit=3)

    assert total == total2 == total3 == 7
    assert len(page1) == 3
    assert len(page2) == 3
    assert len(page3) == 1

    ids = [e["id"] for e in page1 + page2 + page3]
    assert len(ids) == len(set(ids))


def test_add_entry_stores_project_name(isolated_history, isolated_config):
    config.load_config()
    history.add_entry("in", "out", "test-model", project_name="Baby App")
    entries = history.get_entries()
    assert len(entries) == 1
    assert entries[0]["project_name"] == "Baby App"


def test_query_entries_project_filter(isolated_history, isolated_config):
    config.load_config()
    history.add_entry("a", "out1", "m", project_name="Alpha")
    history.add_entry("b", "out2", "m", project_name="Beta")
    page, total = history.query_entries(project="Beta", limit=10)
    assert total == 1
    assert page[0]["project_name"] == "Beta"


def test_query_entries_date_range(isolated_history):
    now = datetime.now(timezone.utc)
    entries = []
    for days_ago in (2, 10, 45, 120):
        entries.append(
            {
                "id": f"id-{days_ago}",
                "timestamp": (now - timedelta(days=days_ago)).isoformat(),
                "input": f"prompt {days_ago}",
                "output": f"out {days_ago}",
                "model": "test-model",
                "tags": [],
                "excluded_from_save": False,
            }
        )
    isolated_history.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    today = now.date()
    start_7 = today - timedelta(days=6)
    start_30 = today - timedelta(days=29)
    start_90 = today - timedelta(days=89)

    _, total_all = history.query_entries(limit=100)
    _, total_7 = history.query_entries(date_from=start_7, date_to=today, limit=100)
    _, total_30 = history.query_entries(date_from=start_30, date_to=today, limit=100)
    _, total_90 = history.query_entries(date_from=start_90, date_to=today, limit=100)

    assert total_all == 4
    assert total_7 == 1
    assert total_30 == 2
    assert total_90 == 3


def test_save_history_false_skips_add_entry(isolated_history, isolated_config):
    config.load_config()
    cfg = config.load_config()
    cfg["save_history"] = False
    config.save_config(cfg)

    history.add_entry("secret prompt", "secret output", "test-model")
    entries = history.get_entries()
    assert entries == []


def test_private_mode_skips_add_entry(isolated_history, isolated_config):
    config.load_config()
    history.add_entry("x", "y", "m", excluded_from_save=True)
    assert history.get_entries() == []


def test_exclude_sensitive_skips_matching_prompt(isolated_history, isolated_config):
    config.load_config()
    cfg = config.load_config()
    cfg["exclude_sensitive"] = True
    cfg["exclude_sensitive_keywords"] = ["password"]
    config.save_config(cfg)

    history.add_entry("my password is 123", "out", "m")
    assert history.get_entries() == []

    history.add_entry("safe prompt", "out", "m")
    assert len(history.get_entries()) == 1
