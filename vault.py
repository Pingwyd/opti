"""
Per-provider API key vault — encrypted at rest via secrets.py (Windows DPAPI).

Keys live in vault.json under the user data directory, separate from config.json.
Plaintext keys never touch disk.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from copy import deepcopy
from typing import Any

from paths import ensure_data_dir, get_data_dir

import secrets

log = logging.getLogger(__name__)

VAULT_VERSION = 1
VAULT_PATH = get_data_dir() / "vault.json"

_vault_lock = threading.Lock()

# Re-import provider list from config at runtime to avoid circular imports.
def _validate_provider(provider: str) -> str:
    from config import VALID_PROVIDERS

    normalized = (provider or "").lower().strip()
    if normalized not in VALID_PROVIDERS:
        raise ValueError(f"provider must be one of: {', '.join(VALID_PROVIDERS)}")
    return normalized


def _default_vault() -> dict[str, Any]:
    return {"version": VAULT_VERSION, "keys": {}}


def load_vault() -> dict[str, Any]:
    """Return vault document (defaults merged with on-disk values)."""
    ensure_data_dir()
    if not VAULT_PATH.exists():
        return _default_vault()
    try:
        with VAULT_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        data = {}
    merged = _default_vault()
    if isinstance(data, dict):
        merged["version"] = int(data.get("version") or VAULT_VERSION)
        keys = data.get("keys")
        if isinstance(keys, dict):
            merged["keys"] = {str(k): str(v) if v is not None else "" for k, v in keys.items()}
    return merged


def save_vault(data: dict[str, Any]) -> None:
    """Atomically write vault.json. Never logs key material."""
    ensure_data_dir()
    payload = deepcopy(data)
    payload["version"] = VAULT_VERSION
    keys = payload.get("keys")
    if not isinstance(keys, dict):
        payload["keys"] = {}
    tmp = VAULT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(VAULT_PATH)


def _decrypt_stored(stored: str) -> str:
    if not stored:
        return ""
    try:
        return secrets.decrypt(stored)
    except (OSError, ValueError):
        return ""


def _encrypt_plaintext(plaintext: str) -> str:
    plain = plaintext.strip()
    return secrets.encrypt(plain) if plain else ""


def get_stored_key(provider: str) -> str:
    """Return decrypted vault key for provider, or '' if none."""
    provider = _validate_provider(provider)
    with _vault_lock:
        vault = load_vault()
        stored = str(vault.get("keys", {}).get(provider) or "")
    return _decrypt_stored(stored)


def has_stored_key(provider: str) -> bool:
    """True when vault has a non-empty encrypted entry for provider."""
    provider = _validate_provider(provider)
    with _vault_lock:
        vault = load_vault()
        stored = str(vault.get("keys", {}).get(provider) or "").strip()
    return bool(stored)


def set_stored_key(provider: str, plaintext: str) -> None:
    """Encrypt and store key for provider; empty string clears the entry."""
    provider = _validate_provider(provider)
    encrypted = _encrypt_plaintext(plaintext)
    with _vault_lock:
        vault = load_vault()
        keys = vault.setdefault("keys", {})
        if encrypted:
            keys[provider] = encrypted
        else:
            keys.pop(provider, None)
        save_vault(vault)


def clear_stored_key(provider: str) -> None:
    set_stored_key(provider, "")


def env_key_for_provider(provider: str) -> str:
    """Return first non-empty env var for provider, or ''."""
    from config import PROVIDER_PRESETS

    provider = _validate_provider(provider)
    for env_name in PROVIDER_PRESETS[provider]["env_keys"]:
        val = (os.environ.get(env_name) or "").strip()
        if val:
            return val
    return ""


def env_key_hint(provider: str) -> str:
    """Helper text when key comes from environment, else ''."""
    from config import PROVIDER_PRESETS

    provider = _validate_provider(provider)
    if has_stored_key(provider):
        return "Stored via DPAPI"
    for env_name in PROVIDER_PRESETS[provider]["env_keys"]:
        if (os.environ.get(env_name) or "").strip():
            return f"Using {env_name} from environment"
    return "Stored via DPAPI"


def resolve_api_key(provider: str) -> str:
    """
    Resolve API key for provider: vault first, then env vars, then ''.
    """
    provider = _validate_provider(provider)
    stored = get_stored_key(provider)
    if stored:
        return stored
    return env_key_for_provider(provider)


def migrate_legacy_api_key(legacy_value: str, provider: str) -> bool:
    """
    Move a legacy config.api_key into vault.keys[provider].

    Returns True when migration ran (legacy value was non-empty).
    """
    legacy = (legacy_value or "").strip()
    if not legacy:
        return False
    provider = _validate_provider(provider)
    with _vault_lock:
        vault = load_vault()
        keys = vault.setdefault("keys", {})
        if provider not in keys or not str(keys.get(provider) or "").strip():
            if secrets.is_encrypted(legacy):
                keys[provider] = legacy
            else:
                keys[provider] = secrets.encrypt(legacy)
            save_vault(vault)
            log.info("Migrated legacy API key into vault for provider %s", provider)
        return True
