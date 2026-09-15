"""Tests for config loading and DPAPI-backed API key storage."""

from __future__ import annotations

import json
import sys

import pytest

import config
import vault
from config import DEFAULT_HOTKEY
import secrets


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point config and vault at temp files so tests never touch real data."""
    config_path = tmp_path / "config.json"
    vault_path = tmp_path / "vault.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(vault, "VAULT_PATH", vault_path)
    return config_path


def test_load_config_defaults(isolated_config):
    cfg = config.load_config()
    assert cfg["provider"] == "gemini"
    assert cfg["hotkey"] == DEFAULT_HOTKEY
    assert cfg["mode"] == "thorough"
    assert cfg["transform"] == "optimize"
    assert cfg["transform_preset"] == ""
    assert cfg["prefill_from_clipboard"] is False
    assert "api_key" not in cfg
    assert isolated_config.exists()


def test_transform_round_trip(isolated_config):
    config.load_config()
    config.set_transform("tone")
    assert config.get_transform() == "tone"
    cfg = config.load_config()
    assert cfg["transform"] == "tone"


def test_set_transform_rejects_invalid(isolated_config):
    config.load_config()
    with pytest.raises(ValueError, match="transform must be"):
        config.set_transform("refine")


def test_transform_preset_round_trip(isolated_config):
    config.load_config()
    config.set_transform_preset("professional")
    assert config.get_transform_preset() == "professional"


def test_prefill_from_clipboard_round_trip(isolated_config):
    config.load_config()
    config.set_prefill_from_clipboard(True)
    assert config.get_prefill_from_clipboard() is True


def test_set_provider_updates_models(isolated_config):
    config.load_config()
    config.set_provider("groq")
    cfg = config.load_config()
    assert cfg["provider"] == "groq"
    assert cfg["model"] == config.PROVIDER_PRESETS["groq"]["model"]


def test_set_provider_openai(isolated_config):
    config.load_config()
    config.set_provider("openai")
    cfg = config.load_config()
    assert cfg["provider"] == "openai"
    assert cfg["model"] == config.PROVIDER_PRESETS["openai"]["model"]
    assert cfg["model_fast"] == config.PROVIDER_PRESETS["openai"]["model_fast"]


def test_api_key_round_trip(isolated_config):
    config.load_config()
    config.set_api_key("test-secret-key-12345")
    assert config.get_api_key() == "test-secret-key-12345"

    raw = json.loads(vault.VAULT_PATH.read_text(encoding="utf-8"))
    stored = raw["keys"]["gemini"]
    if sys.platform == "win32":
        assert stored.startswith(secrets.DPAPI_PREFIX)
        assert secrets.decrypt(stored) == "test-secret-key-12345"
    else:
        assert stored == "test-secret-key-12345"

    raw_cfg = json.loads(isolated_config.read_text(encoding="utf-8"))
    assert "api_key" not in raw_cfg


def test_plaintext_key_migrated_on_load(isolated_config):
    isolated_config.write_text(
        json.dumps({"api_key": "legacy-plain-key", "provider": "gemini"}),
        encoding="utf-8",
    )
    assert config.get_api_key() == "legacy-plain-key"
    raw = json.loads(isolated_config.read_text(encoding="utf-8"))
    assert "api_key" not in raw


def test_has_api_key_false_when_empty(isolated_config):
    config.load_config()
    assert config.has_api_key() is False
