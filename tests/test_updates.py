"""Tests for GitHub update checking."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import updates
from updates import (
    UpdateCheckResult,
    check_for_updates,
    is_version_newer,
    normalize_version,
    parse_version_tuple,
)


def test_parse_version_tuple():
    assert parse_version_tuple("1.2.0") == (1, 2, 0)
    assert parse_version_tuple("v1.2.0") == (1, 2, 0)
    assert parse_version_tuple("2.0") == (2, 0)


def test_is_version_newer():
    assert is_version_newer("1.2.0", "1.1.0")
    assert not is_version_newer("1.1.0", "1.2.0")
    assert not is_version_newer("1.2.0", "1.2.0")


def test_check_for_updates_up_to_date(monkeypatch):
    payload = json.dumps({"tag_name": "v1.2.0", "html_url": "https://example.com/r"}).encode()

    def fake_urlopen(_req, timeout=0):
        assert timeout == updates.REQUEST_TIMEOUT_SEC
        resp = MagicMock()
        resp.read.return_value = payload
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda *a: None
        return resp

    monkeypatch.setattr(updates.urllib.request, "urlopen", fake_urlopen)
    result = check_for_updates("1.2.0")
    assert result.status == "up_to_date"
    assert result.latest_version == "1.2.0"


def test_check_for_updates_update_available(monkeypatch):
    payload = json.dumps({"tag_name": "v1.3.0", "html_url": "https://example.com/new"}).encode()

    def fake_urlopen(_req, timeout=0):
        resp = MagicMock()
        resp.read.return_value = payload
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda *a: None
        return resp

    monkeypatch.setattr(updates.urllib.request, "urlopen", fake_urlopen)
    result = check_for_updates("1.2.0")
    assert result.status == "update_available"
    assert result.latest_version == "1.3.0"
    assert result.release_url == "https://example.com/new"


def test_normalize_version():
    assert normalize_version("v1.0.0") == "1.0.0"
