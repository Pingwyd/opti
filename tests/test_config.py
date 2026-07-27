"""Tests for config loading and DPAPI-backed API key storage."""

from __future__ import annotations

import json
import sys

import pytest

import config
from config import DEFAULT_HOTKEY
import secrets


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point config at a temp file so tests never touch the real config.json."""
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    return config_path


def test_load_config_defaults(isolated_config):
    cfg = config.load_config()
    assert cfg["provider"] == "gemini"
    assert cfg["hotkey"] == DEFAULT_HOTKEY
    assert cfg["mode"] == "thorough"
    assert isolated_config.exists()


def test_set_provider_updates_models(isolated_config):
    config.load_config()
    config.set_provider("groq")
    cfg = config.load_config()
    assert cfg["provider"] == "groq"
    assert cfg["model"] == config.PROVIDER_PRESETS["groq"]["model"]


def test_api_key_round_trip(isolated_config):
    config.load_config()
    config.set_api_key("test-secret-key-12345")
    assert config.get_api_key() == "test-secret-key-12345"

    raw = json.loads(isolated_config.read_text(encoding="utf-8"))
    stored = raw["api_key"]
    if sys.platform == "win32":
        assert stored.startswith(secrets.DPAPI_PREFIX)
        assert secrets.decrypt(stored) == "test-secret-key-12345"
    else:
        assert stored == "test-secret-key-12345"


def test_plaintext_key_migrated_on_load(isolated_config):
    isolated_config.write_text(
        json.dumps({"api_key": "legacy-plain-key", "provider": "gemini"}),
        encoding="utf-8",
    )
    assert config.get_api_key() == "legacy-plain-key"
    raw = json.loads(isolated_config.read_text(encoding="utf-8"))
    if sys.platform == "win32":
        assert raw["api_key"].startswith(secrets.DPAPI_PREFIX)
    else:
        assert raw["api_key"] == "legacy-plain-key"


def test_has_api_key_false_when_empty(isolated_config):
    config.load_config()
    assert config.has_api_key() is False
