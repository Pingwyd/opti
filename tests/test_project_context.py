"""Tests for project context storage and prompt injection."""

from __future__ import annotations

import pytest

import config
import projects as projects_mod
from projects import (
    PROJECT_TYPES,
    create_project,
    delete_project,
    get_active_project,
    list_projects,
    parse_tech_stack_input,
    set_active_project,
    slug_from_name,
    unique_project_id,
    update_project,
)
from prompt import SYSTEM_PROMPT, build_system_prompt, format_project_context_block, inject_project_context


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    projects_path = tmp_path / "projects.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(projects_mod, "PROJECTS_PATH", projects_path)
    monkeypatch.setattr(projects_mod, "_legacy_migrated", False)
    return config_path


def test_migrate_projects_from_legacy_config(isolated_config, monkeypatch):
    import json

    isolated_config.write_text(
        json.dumps(
            {
                "provider": "gemini",
                "projects": {
                    "legacy-one": {
                        "name": "Legacy",
                        "tech_stack": ["Go"],
                        "project_type": "",
                        "conventions": "",
                        "notes": "",
                        "default_transform": "optimize",
                        "created": "2026-01-01T00:00:00Z",
                        "last_used": "2026-01-01T00:00:00Z",
                        "updated": "2026-01-01T00:00:00Z",
                    }
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(projects_mod, "_legacy_migrated", False)
    items = list_projects()
    assert len(items) == 1
    assert items[0]["name"] == "Legacy"
    assert "projects" not in config.load_config()
    assert projects_mod.PROJECTS_PATH.is_file()


def test_slug_from_name_basic():
    assert slug_from_name("Baby App") == "baby-app"
    assert slug_from_name("  My_Project!!  ") == "my-project"


def test_unique_project_id_suffixes():
    projects = {"baby-app": {"name": "Baby App"}}
    assert unique_project_id("Baby App", projects) == "baby-app-2"


def test_project_types_includes_desktop_app():
    assert "Desktop app" in PROJECT_TYPES


def test_parse_tech_stack_input_comma_separated():
    assert parse_tech_stack_input("Python, PyQt6, pynput") == [
        "Python",
        "PyQt6",
        "pynput",
    ]


def test_parse_tech_stack_input_newlines():
    assert parse_tech_stack_input("Python\nPyQt6\npynput") == [
        "Python",
        "PyQt6",
        "pynput",
    ]


def test_parse_tech_stack_input_mixed_and_deduped():
    assert parse_tech_stack_input(" Python, PyQt6\npython, ,PyQt6 ") == [
        "Python",
        "PyQt6",
    ]


def test_create_project_accepts_desktop_app_type(isolated_config):
    config.load_config()
    project_id = create_project(name="MetaPrompt", project_type="Desktop app")
    project = get_active_project() or list_projects()[0]
    assert project_id
    assert project["project_type"] == "Desktop app"


def test_project_crud_round_trip(isolated_config):
    config.load_config()
    project_id = create_project(
        name="Baby App",
        tech_stack=["React Native", "TypeScript"],
        project_type="Mobile app",
        conventions="Use agents.md",
        notes="Expo app",
    )
    assert project_id == "baby-app"

    active = get_active_project()
    assert active is None

    set_active_project(project_id)
    active = get_active_project()
    assert active is not None
    assert active["name"] == "Baby App"
    assert active["tech_stack"] == ["React Native", "TypeScript"]

    update_project(
        project_id,
        name="Baby App",
        tech_stack=["Expo"],
        project_type="Mobile app",
        conventions="Updated conventions",
        notes="",
    )
    updated = get_active_project()
    assert updated is not None
    assert updated["tech_stack"] == ["Expo"]
    assert updated["conventions"] == "Updated conventions"

    projects = list_projects()
    assert len(projects) == 1
    assert projects[0]["id"] == "baby-app"

    delete_project(project_id)
    assert list_projects() == []
    assert get_active_project() is None


def test_create_project_requires_name(isolated_config):
    config.load_config()
    with pytest.raises(ValueError, match="name"):
        create_project(name="   ")


def test_format_project_context_empty():
    assert format_project_context_block(None) == ""
    assert format_project_context_block({}) == ""
    assert format_project_context_block({"name": "", "tech_stack": []}) == ""


def test_format_project_context_partial():
    block = format_project_context_block(
        {
            "name": "Baby App",
            "project_type": "",
            "tech_stack": ["TypeScript"],
            "conventions": "",
            "notes": "",
        }
    )
    assert "- Project: Baby App" in block
    assert "- Tech stack: TypeScript" in block
    assert "Conventions:" not in block
    assert "Additional notes:" not in block


def test_format_project_context_full():
    block = format_project_context_block(
        {
            "name": "Baby App",
            "project_type": "Mobile app",
            "tech_stack": ["React Native", "Expo"],
            "conventions": "Shake invalid fields",
            "notes": "Supabase backend",
        }
    )
    assert "- Project: Baby App (Mobile app)" in block
    assert "- Tech stack: React Native, Expo" in block
    assert "- Conventions: Shake invalid fields" in block
    assert "- Additional notes: Supabase backend" in block


def test_inject_project_context_prepends_block():
    project = {
        "name": "CLI",
        "project_type": "CLI tool",
        "tech_stack": ["Python"],
        "conventions": "",
        "notes": "",
    }
    result = inject_project_context(SYSTEM_PROMPT, project)
    assert result.startswith("Project context")
    assert result.endswith(SYSTEM_PROMPT)


def test_build_system_prompt_private_mode_excludes_context():
    project = {
        "name": "Baby App",
        "project_type": "Mobile app",
        "tech_stack": ["Expo"],
        "conventions": "",
        "notes": "",
    }
    assert build_system_prompt(project, private_mode=True, include_in_private=False) == SYSTEM_PROMPT


def test_build_system_prompt_private_mode_optional_include():
    project = {
        "name": "Baby App",
        "project_type": "Mobile app",
        "tech_stack": ["Expo"],
        "conventions": "",
        "notes": "",
    }
    result = build_system_prompt(project, private_mode=True, include_in_private=True)
    assert "Project context" in result
    assert SYSTEM_PROMPT in result


def test_project_default_transform_round_trip(isolated_config):
    config.load_config()
    project_id = create_project(name="Writing", default_transform="tone")
    project = get_active_project() or list_projects()[0]
    assert project["default_transform"] == "tone"

    update_project(
        project_id,
        name="Writing",
        tech_stack=[],
        project_type="",
        conventions="",
        notes="",
        default_transform="extract",
    )
    updated = list_projects()[0]
    assert updated["default_transform"] == "extract"


def test_create_project_rejects_invalid_default_transform(isolated_config):
    config.load_config()
    with pytest.raises(ValueError, match="default_transform"):
        create_project(name="Bad", default_transform="refine")


def test_get_effective_transform_matches_session_transform(isolated_config):
    config.load_config()
    config.set_transform("summarize")
    assert config.get_effective_transform() == "summarize"


def test_project_default_transform_applied_on_switch(isolated_config):
    config.load_config()
    config.set_transform("summarize")
    project_id = create_project(name="Email", default_transform="tone")
    set_active_project(project_id)
    project = get_active_project()
    assert project is not None
    config.set_transform(str(project.get("default_transform")))
    assert config.get_effective_transform() == "tone"
