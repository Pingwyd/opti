"""Tests for settings/projects backup export and import."""

from __future__ import annotations

import json

import pytest

import backup
import config
import projects as projects_mod
import vault
from backup import (
    BACKUP_FORMAT,
    ImportMode,
    build_backup_document,
    exportable_config,
    import_from_document,
    load_backup_from_path,
    validate_backup_document,
)
from vault import clear_stored_key, get_stored_key, set_stored_key


@pytest.fixture
def isolated_data(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    vault_path = tmp_path / "vault.json"
    projects_path = tmp_path / "projects.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(vault, "VAULT_PATH", vault_path)
    monkeypatch.setattr(projects_mod, "PROJECTS_PATH", projects_path)
    monkeypatch.setattr(projects_mod, "_legacy_migrated", True)
    config.save_config(
        {
            "provider": "gemini",
            "window_x": 10,
            "window_y": 20,
        }
    )
    projects_mod.save_projects_store(
        {
            "alpha": {
                "name": "Alpha",
                "tech_stack": ["Python"],
                "project_type": "Desktop app",
                "conventions": "Use type hints",
                "notes": "",
                "default_transform": "optimize",
                "created": "2026-01-01T00:00:00Z",
                "last_used": "2026-01-01T00:00:00Z",
                "updated": "2026-01-01T00:00:00Z",
            }
        }
    )
    set_stored_key("gemini", "test-key-123")
    return tmp_path


def test_exportable_config_strips_geometry_and_api_key(isolated_data):
    cfg = exportable_config()
    assert "window_x" not in cfg
    assert "window_y" not in cfg
    assert "api_key" not in cfg
    assert "projects" not in cfg


def test_build_backup_document_shape(isolated_data):
    doc = build_backup_document()
    assert doc["format"] == BACKUP_FORMAT
    assert doc["format_version"] == 2
    assert doc["vault_keys"]["gemini"] == "test-key-123"
    assert "window_x" not in doc["config"]
    assert doc["projects"]["alpha"]["name"] == "Alpha"


def test_export_import_round_trip(isolated_data, tmp_path):
    path = tmp_path / "backup.opti.json"
    backup.export_to_path(path)
    loaded = load_backup_from_path(path)
    validate_backup_document(loaded)

    config.save_config({"provider": "groq"})
    projects_mod.replace_projects_store({})
    vault.clear_stored_key("gemini")

    result = import_from_document(loaded, mode=ImportMode.REPLACE)
    cfg = config.load_config()
    store = projects_mod.load_projects_store()
    assert cfg["provider"] == "gemini"
    assert store["alpha"]["tech_stack"] == ["Python"]
    assert vault.get_stored_key("gemini") == "test-key-123"
    assert result.vault_keys_imported == 1
    assert store["alpha"]["conventions"] == "Use type hints"


def test_merge_renames_conflicting_project(isolated_data):
    projects_mod.replace_projects_store(
        {
            "alpha": {
                "name": "Existing",
                "tech_stack": [],
                "project_type": "",
                "conventions": "",
                "notes": "",
                "default_transform": "optimize",
                "created": "2026-01-01T00:00:00Z",
                "last_used": "2026-01-01T00:00:00Z",
                "updated": "2026-01-01T00:00:00Z",
            }
        }
    )
    doc = build_backup_document()
    result = import_from_document(doc, mode=ImportMode.MERGE)
    store = projects_mod.load_projects_store()
    assert "alpha" in store
    assert any(k.startswith("alpha") for k in store)
    assert result.projects_renamed


def test_invalid_backup_raises(isolated_data):
    with pytest.raises(backup.BackupError):
        validate_backup_document({"format": "wrong"})


def test_draft_helpers():
    from settings_ui import draft_to_update_kwargs, project_draft_from_record

    record = {
        "name": "App",
        "project_type": "Web app",
        "tech_stack": ["Python", "Vue"],
        "conventions": "Tabs not spaces",
        "notes": "Ship Friday",
        "inject_process": "code.exe",
        "default_transform": "summarize",
    }
    draft = project_draft_from_record(record)
    assert "Python, Vue" in draft["tech_stack_text"]
    kwargs = draft_to_update_kwargs(draft)
    assert kwargs["tech_stack"] == ["Python", "Vue"]
    assert kwargs["name"] == "App"
