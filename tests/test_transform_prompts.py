"""Tests for transform-mode system prompts."""

from __future__ import annotations

import pytest

from api import resolve_system_prompt
from prompt import (
    ASK_PROMPT,
    EXTRACT_PROMPT,
    SUMMARIZE_PROMPT,
    SYSTEM_PROMPT,
    TONE_PROMPT,
    TRANSFORM_PROMPTS,
    VALID_TRANSFORMS,
    build_system_prompt,
    get_transform_prompt,
    normalize_transform,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("optimize", "optimize"),
        ("TONE", "tone"),
        ("summarize", "summarize"),
        ("extract", "extract"),
        ("ask", "ask"),
        ("ASK", "ask"),
        ("invalid", "optimize"),
        ("", "optimize"),
        (None, "optimize"),
    ],
)
def test_normalize_transform(raw, expected):
    assert normalize_transform(raw) == expected


def test_valid_transforms_match_prompts():
    assert VALID_TRANSFORMS == tuple(TRANSFORM_PROMPTS.keys())


def test_get_transform_prompt_returns_expected_base():
    assert get_transform_prompt("optimize") == SYSTEM_PROMPT
    assert get_transform_prompt("tone") == TONE_PROMPT
    assert get_transform_prompt("summarize") == SUMMARIZE_PROMPT
    assert get_transform_prompt("extract") == EXTRACT_PROMPT
    assert get_transform_prompt("ask") == ASK_PROMPT
    assert get_transform_prompt("unknown") == SYSTEM_PROMPT


def test_build_system_prompt_optimize_includes_project_context():
    project = {
        "name": "Opti",
        "project_type": "Desktop app",
        "tech_stack": ["Python"],
        "conventions": "",
        "notes": "",
    }
    result = build_system_prompt(project, transform="optimize")
    assert result.startswith("Project context")
    assert SYSTEM_PROMPT in result
    assert "rewritten prompt" in result.lower()


def test_build_system_prompt_tone_uses_light_context_footer():
    project = {
        "name": "Writing",
        "project_type": "",
        "tech_stack": [],
        "conventions": "Client-facing",
        "notes": "",
    }
    result = build_system_prompt(project, transform="tone")
    assert "client-facing" in result.lower() or "Client-facing" in result
    assert TONE_PROMPT in result
    assert "Use this context only when it helps audience" in result


def test_build_system_prompt_summarize_private_mode_omits_context():
    project = {
        "name": "Research",
        "project_type": "",
        "tech_stack": ["Python"],
        "conventions": "",
        "notes": "",
    }
    result = build_system_prompt(
        project,
        private_mode=True,
        include_in_private=False,
        transform="summarize",
    )
    assert result == SUMMARIZE_PROMPT
    assert "Project context" not in result


def test_build_system_prompt_ask_private_mode_omits_context():
    project = {
        "name": "Dev",
        "project_type": "Desktop app",
        "tech_stack": ["Python"],
        "conventions": "",
        "notes": "",
    }
    result = build_system_prompt(
        project,
        private_mode=True,
        include_in_private=False,
        transform="ask",
    )
    assert result == ASK_PROMPT
    assert "Project context" not in result


def test_build_system_prompt_ask_uses_light_context():
    project = {
        "name": "Dev",
        "project_type": "Desktop app",
        "tech_stack": ["Python"],
        "conventions": "",
        "notes": "",
    }
    result = build_system_prompt(project, transform="ask")
    assert ASK_PROMPT in result
    assert "Use this context only when it helps audience" in result


def test_build_system_prompt_extract_has_fixed_sections():
    result = build_system_prompt(None, transform="extract")
    assert "Key facts" in result
    assert "Decisions" in result
    assert "Action items" in result


def test_build_system_prompt_appends_preset():
    result = build_system_prompt(None, transform="tone", transform_preset="professional")
    assert "Output format preset: professional" in result


def test_resolve_system_prompt_uses_config_transform(isolated_config, monkeypatch):
    import config

    config.load_config()
    config.set_transform("summarize")
    prompt = resolve_system_prompt()
    assert SUMMARIZE_PROMPT in prompt


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    import config

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    return config_path
