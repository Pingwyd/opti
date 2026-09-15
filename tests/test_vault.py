"""Tests for per-provider API key vault."""

from __future__ import annotations

import json
import sys

import pytest

import config
import secrets
import vault
from vault import (
    clear_stored_key,
    get_stored_key,
    has_stored_key,
    migrate_legacy_api_key,
    resolve_api_key,
    set_stored_key,
)


@pytest.fixture
def isolated_vault(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    vault_path = tmp_path / "vault.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(vault, "VAULT_PATH", vault_path)
    return vault_path


def test_vault_stores_per_provider(isolated_vault):
    set_stored_key("gemini", "gem-secret")
    set_stored_key("groq", "groq-secret")
    assert get_stored_key("gemini") == "gem-secret"
    assert get_stored_key("groq") == "groq-secret"
    assert has_stored_key("anthropic") is False


def test_vault_encrypts_at_rest(isolated_vault):
    set_stored_key("gemini", "test-secret-key-12345")
    raw = json.loads(isolated_vault.read_text(encoding="utf-8"))
    stored = raw["keys"]["gemini"]
    if sys.platform == "win32":
        assert stored.startswith(secrets.DPAPI_PREFIX)
        assert secrets.decrypt(stored) == "test-secret-key-12345"
    else:
        assert stored == "test-secret-key-12345"


def test_clear_stored_key(isolated_vault):
    set_stored_key("gemini", "x")
    clear_stored_key("gemini")
    assert not has_stored_key("gemini")
    assert get_stored_key("gemini") == ""


def test_provider_switch_uses_correct_key(isolated_vault):
    config.load_config()
    set_stored_key("gemini", "g1")
    set_stored_key("anthropic", "a1")
    config.set_provider("gemini")
    assert config.get_api_key() == "g1"
    config.set_provider("anthropic")
    assert config.get_api_key() == "a1"


def test_env_fallback_when_no_vault_key(isolated_vault, monkeypatch):
    config.load_config()
    config.set_provider("groq")
    monkeypatch.setenv("GROQ_API_KEY", "env-groq")
    assert resolve_api_key("groq") == "env-groq"
    assert has_stored_key("groq") is False


def test_vault_key_takes_precedence_over_env(isolated_vault, monkeypatch):
    config.load_config()
    config.set_provider("groq")
    monkeypatch.setenv("GROQ_API_KEY", "env-groq")
    set_stored_key("groq", "vault-groq")
    assert resolve_api_key("groq") == "vault-groq"


def test_migrate_legacy_api_key(isolated_vault):
    encrypted = secrets.encrypt("legacy-key")
    assert migrate_legacy_api_key(encrypted, "gemini") is True
    assert get_stored_key("gemini") == "legacy-key"


def test_migrate_legacy_plaintext_encrypts(isolated_vault):
    assert migrate_legacy_api_key("plain-legacy", "gemini") is True
    raw = json.loads(isolated_vault.read_text(encoding="utf-8"))
    stored = raw["keys"]["gemini"]
    if sys.platform == "win32":
        assert stored.startswith(secrets.DPAPI_PREFIX)
    assert get_stored_key("gemini") == "plain-legacy"


def test_env_fallback_openai(isolated_vault, monkeypatch):
    config.load_config()
    config.set_provider("openai")
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai")
    assert resolve_api_key("openai") == "env-openai"


def test_load_config_migrates_legacy_api_key_from_config(isolated_vault, monkeypatch):
    config_path = isolated_vault.parent / "config.json"
    config_path.write_text(
        json.dumps({"api_key": "legacy-plain-key", "provider": "gemini"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    assert config.get_api_key() == "legacy-plain-key"
    raw_cfg = json.loads(config_path.read_text(encoding="utf-8"))
    assert "api_key" not in raw_cfg
    assert get_stored_key("gemini") == "legacy-plain-key"
