"""
Export / import Opti settings, projects, and API keys for backup or migration.

Backup files contain plaintext API keys — treat like a password export.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from brand import APP_VERSION
from config import load_config, save_config
from projects import load_projects_store, replace_projects_store, save_projects_store, unique_project_id
from vault import get_stored_key, set_stored_key

log = logging.getLogger(__name__)

BACKUP_FORMAT = "opti-backup"
BACKUP_FORMAT_VERSION = 2

GEOMETRY_KEYS = frozenset(
    {
        "window_x",
        "window_y",
        "chip_x",
        "chip_y",
        "settings_window_x",
        "settings_window_y",
        "settings_window_w",
        "settings_window_h",
        "history_window_x",
        "history_window_y",
        "history_window_w",
        "history_window_h",
        "history_split_ratio",
    }
)


class ImportMode(str, Enum):
    MERGE = "merge"
    REPLACE = "replace"


@dataclass
class ImportResult:
    settings_keys_updated: int = 0
    projects_added: int = 0
    projects_renamed: list[str] = field(default_factory=list)
    vault_keys_imported: int = 0


class BackupError(ValueError):
    """Invalid or unsupported backup file."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def exportable_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return config suitable for backup (no legacy api_key, no geometry)."""
    cfg = deepcopy(config if config is not None else load_config())
    cfg.pop("api_key", None)
    cfg.pop("projects", None)
    for key in GEOMETRY_KEYS:
        cfg.pop(key, None)
    return cfg


def _collect_vault_keys_plaintext() -> dict[str, str]:
    from config import VALID_PROVIDERS as providers

    keys: dict[str, str] = {}
    for provider in providers:
        plain = get_stored_key(provider)
        if plain:
            keys[provider] = plain
    return keys


def build_backup_document() -> dict[str, Any]:
    return {
        "format": BACKUP_FORMAT,
        "format_version": BACKUP_FORMAT_VERSION,
        "exported_at": _utc_now_iso(),
        "app_version": APP_VERSION,
        "config": exportable_config(),
        "projects": load_projects_store(),
        "vault_keys": _collect_vault_keys_plaintext(),
    }


def export_to_path(path: Path | str) -> None:
    """Write backup JSON to path."""
    doc = build_backup_document()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log.info("Settings backup exported to %s", target)


def validate_backup_document(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise BackupError("Backup file must be a JSON object.")
    if data.get("format") != BACKUP_FORMAT:
        raise BackupError("Unrecognized backup format.")
    version = int(data.get("format_version") or 0)
    if version not in (1, BACKUP_FORMAT_VERSION):
        raise BackupError(f"Unsupported backup version {version}.")
    config = data.get("config")
    if not isinstance(config, dict):
        raise BackupError("Backup is missing config object.")
    vault_keys = data.get("vault_keys")
    if vault_keys is not None and not isinstance(vault_keys, dict):
        raise BackupError("Backup vault_keys must be an object.")
    return data


def load_backup_from_path(path: Path | str) -> dict[str, Any]:
    try:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupError("Could not read backup file.") from exc
    return validate_backup_document(data)


def _projects_from_backup_document(data: dict[str, Any]) -> dict[str, Any]:
    top = data.get("projects")
    if isinstance(top, dict):
        return top
    config = data.get("config") or {}
    legacy = config.get("projects")
    if isinstance(legacy, dict):
        return legacy
    return {}


def backup_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Non-secret preview for import dialog."""
    projects = _projects_from_backup_document(data)
    vault_keys = data.get("vault_keys") if isinstance(data.get("vault_keys"), dict) else {}
    providers = [k for k, v in vault_keys.items() if str(v).strip()]
    return {
        "app_version": str(data.get("app_version") or ""),
        "exported_at": str(data.get("exported_at") or ""),
        "project_count": len(projects),
        "providers_with_keys": providers,
    }


def _merge_config(current: dict[str, Any], incoming: dict[str, Any]) -> tuple[dict[str, Any], int]:
    merged = deepcopy(current)
    updated = 0
    for key, value in incoming.items():
        if key in GEOMETRY_KEYS:
            continue
        if key in ("api_key", "projects"):
            continue
        merged[key] = deepcopy(value)
        updated += 1
    return merged, updated


def _import_vault_keys(vault_keys: dict[str, Any]) -> int:
    from config import VALID_PROVIDERS as providers

    count = 0
    for provider, plain in vault_keys.items():
        if provider not in providers:
            continue
        text = str(plain or "").strip()
        if not text:
            continue
        set_stored_key(provider, text)
        count += 1
    return count


def _merge_projects(
    current_projects: dict[str, Any], incoming_projects: dict[str, Any]
) -> tuple[dict[str, Any], int, list[str]]:
    result = deepcopy(current_projects)
    added = 0
    renamed: list[str] = []
    for project_id, payload in incoming_projects.items():
        if not isinstance(payload, dict):
            continue
        target_id = str(project_id)
        if target_id in result:
            name = str(payload.get("name") or target_id)
            new_id = unique_project_id(name, result)
            renamed.append(f"{target_id} → {new_id}")
            target_id = new_id
        added += 1
        result[target_id] = deepcopy(payload)
    return result, added, renamed


def import_from_document(data: dict[str, Any], *, mode: ImportMode) -> ImportResult:
    """Apply backup to live config + vault. Raises BackupError on invalid input."""
    doc = validate_backup_document(data)
    incoming_cfg = exportable_config(doc["config"])
    incoming_projects = _projects_from_backup_document(doc)
    current = load_config()
    result = ImportResult()

    if mode == ImportMode.REPLACE:
        merged, count = _merge_config(current, incoming_cfg)
        result.settings_keys_updated = count
        save_config(merged)
        if incoming_projects:
            replace_projects_store(deepcopy(incoming_projects))
            result.projects_added = len(incoming_projects)
    else:
        merged = deepcopy(current)
        merged_cfg, count = _merge_config(merged, incoming_cfg)
        result.settings_keys_updated = count
        cur_projects = load_projects_store()
        if incoming_projects:
            merged_projects, added, renamed = _merge_projects(cur_projects, incoming_projects)
            save_projects_store(merged_projects)
            result.projects_added = added
            result.projects_renamed = renamed
        active = incoming_cfg.get("active_project")
        if active and active in load_projects_store():
            merged_cfg["active_project"] = active
        save_config(merged_cfg)

    vault_keys = doc.get("vault_keys")
    if isinstance(vault_keys, dict):
        result.vault_keys_imported = _import_vault_keys(vault_keys)

    return result


def import_from_path(path: Path | str, *, mode: ImportMode) -> ImportResult:
    return import_from_document(load_backup_from_path(path), mode=mode)
