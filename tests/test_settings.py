"""Tests for settings persistence and dialog construction."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

import config
from config import (
    DEFAULT_HOTKEY,
    DEFAULT_HOTKEY_COLLAPSE,
    DEFAULT_SHORTCUT_COLLAPSE,
    DEFAULT_SHORTCUT_HIDE_TRAY,
    DEFAULT_SHORTCUT_PRIVATE,
    key_sequence_from_string,
    normalize_shortcut_string,
    shortcuts_equal,
)
from settings_ui import (
    HISTORY_LIMIT_MAX,
    HISTORY_LIMIT_MIN,
    SettingsDialog,
    apply_settings_values,
    build_settings_values,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    return config_path


def _base_settings_kwargs(**overrides):
    defaults = {
        "provider": "gemini",
        "api_key_input": "",
        "hotkey": "ctrl+shift+space",
        "hotkey_collapse": DEFAULT_HOTKEY_COLLAPSE,
        "model": "gemini-3.5-flash",
        "model_fast": "gemini-3.1-flash-lite",
        "mode": "thorough",
        "persist_draft": True,
        "save_history": True,
        "exclude_sensitive": False,
        "history_limit": 50,
        "start_with_windows": False,
        "shortcut_collapse": DEFAULT_SHORTCUT_COLLAPSE,
        "shortcut_hide_tray": DEFAULT_SHORTCUT_HIDE_TRAY,
        "shortcut_private": DEFAULT_SHORTCUT_PRIVATE,
        "auto_copy_clipboard": True,
    }
    defaults.update(overrides)
    return defaults


def test_build_settings_values_clamps_history_limit():
    values = build_settings_values(**_base_settings_kwargs(history_limit=99999))
    assert values["history_limit"] == HISTORY_LIMIT_MAX

    values = build_settings_values(
        **_base_settings_kwargs(
            mode="fast",
            persist_draft=False,
            save_history=False,
            exclude_sensitive=True,
            history_limit=1,
            shortcut_collapse="Ctrl+Shift+M",
            shortcut_hide_tray="Escape",
            auto_copy_clipboard=False,
        )
    )
    assert values["history_limit"] == HISTORY_LIMIT_MIN
    assert values["mode"] == "fast"


def test_apply_settings_values_round_trip(isolated_config):
    config.load_config()
    values = build_settings_values(
        **_base_settings_kwargs(
            provider="groq",
            api_key_input="secret-key-abc",
            hotkey="ctrl+shift+space",
            model="llama-3.3-70b-versatile",
            model_fast="llama-3.1-8b-instant",
            mode="fast",
            persist_draft=False,
            save_history=False,
            exclude_sensitive=True,
            history_limit=200,
            shortcut_collapse="Ctrl+Shift+M",
            shortcut_hide_tray="Escape",
        )
    )
    assert apply_settings_values(values) is None

    cfg = config.load_config()
    assert cfg["provider"] == "groq"
    assert cfg["hotkey"] == "Ctrl+Shift+Space"
    assert cfg["model"] == "llama-3.3-70b-versatile"
    assert cfg["model_fast"] == "llama-3.1-8b-instant"
    assert cfg["mode"] == "fast"
    assert cfg["persist_draft"] is False
    assert cfg["save_history"] is False
    assert cfg["exclude_sensitive"] is True
    assert cfg["history_limit"] == 200
    assert config.get_api_key() == "secret-key-abc"


def test_apply_settings_requires_api_key_on_first_run(isolated_config):
    config.load_config()
    values = build_settings_values(**_base_settings_kwargs())
    assert apply_settings_values(values, require_api_key=True) == "API key cannot be empty."


def test_settings_dialog_instantiation(qapp, isolated_config):
    config.load_config()
    dlg = SettingsDialog()
    assert dlg.windowTitle() == "MetaPrompt settings"

    first_run = SettingsDialog(first_run=True)
    assert first_run.windowTitle() == "MetaPrompt setup"


def test_shortcut_config_defaults(isolated_config):
    cfg = config.load_config()
    assert cfg["shortcut_collapse"] == DEFAULT_SHORTCUT_COLLAPSE
    assert cfg["shortcut_hide_tray"] == DEFAULT_SHORTCUT_HIDE_TRAY
    assert cfg["shortcut_private"] == DEFAULT_SHORTCUT_PRIVATE
    assert cfg["auto_copy_clipboard"] is True


def test_shortcut_config_round_trip(isolated_config):
    config.load_config()
    config.set_shortcut_collapse("Ctrl+Alt+C")
    config.set_shortcut_hide_tray("F12")
    config.set_shortcut_private("Ctrl+Shift+U")
    config.set_auto_copy_clipboard(False)

    assert config.get_shortcut_collapse() == "Ctrl+Alt+C"
    assert config.get_shortcut_hide_tray() == "F12"
    assert config.get_shortcut_private() == "Ctrl+Shift+U"
    assert config.get_auto_copy_clipboard() is False

    cfg = config.load_config()
    assert cfg["shortcut_collapse"] == "Ctrl+Alt+C"
    assert cfg["shortcut_hide_tray"] == "F12"
    assert cfg["shortcut_private"] == "Ctrl+Shift+U"
    assert cfg["auto_copy_clipboard"] is False


def test_normalize_shortcut_string_empty_reverts_to_default():
    assert normalize_shortcut_string("", DEFAULT_SHORTCUT_COLLAPSE) == DEFAULT_SHORTCUT_COLLAPSE
    assert normalize_shortcut_string("   ", DEFAULT_SHORTCUT_HIDE_TRAY) == DEFAULT_SHORTCUT_HIDE_TRAY
    assert normalize_shortcut_string("", DEFAULT_SHORTCUT_PRIVATE) == DEFAULT_SHORTCUT_PRIVATE


def test_key_sequence_from_string_parses_shortcut():
    seq = key_sequence_from_string("Ctrl+Shift+M")
    assert not seq.isEmpty()
    assert seq.toString() == "Ctrl+Shift+M"


def test_apply_settings_rejects_duplicate_shortcuts(isolated_config):
    config.load_config()
    values = build_settings_values(
        **_base_settings_kwargs(
            shortcut_collapse="Ctrl+Shift+M",
            shortcut_hide_tray="Ctrl+Shift+M",
        )
    )
    assert apply_settings_values(values) == "In-app shortcuts must each be unique."


def test_apply_settings_rejects_private_shortcut_duplicate(isolated_config):
    config.load_config()
    values = build_settings_values(
        **_base_settings_kwargs(
            shortcut_collapse="Ctrl+Shift+M",
            shortcut_hide_tray="Escape",
            shortcut_private="Ctrl+Shift+M",
        )
    )
    assert apply_settings_values(values) == "In-app shortcuts must each be unique."


def test_apply_settings_rejects_global_hotkey_matching_shortcut(isolated_config):
    config.load_config()
    values = build_settings_values(
        **_base_settings_kwargs(
            hotkey="Ctrl+Shift+M",
            shortcut_collapse="Ctrl+Shift+M",
            shortcut_hide_tray="Escape",
        )
    )
    assert (
        apply_settings_values(values)
        == "Global hotkeys cannot match an in-app shortcut."
    )


def test_apply_settings_rejects_global_hotkey_matching_private(isolated_config):
    config.load_config()
    values = build_settings_values(
        **_base_settings_kwargs(
            hotkey="Ctrl+Shift+P",
            shortcut_private="Ctrl+Shift+P",
        )
    )
    assert (
        apply_settings_values(values)
        == "Global hotkeys cannot match an in-app shortcut."
    )


def test_apply_settings_rejects_duplicate_global_hotkeys(isolated_config):
    config.load_config()
    values = build_settings_values(
        **_base_settings_kwargs(
            hotkey="Ctrl+Shift+Space",
            hotkey_collapse="Ctrl+Shift+Space",
        )
    )
    assert apply_settings_values(values) == "Global hotkeys must each be unique."


def test_apply_settings_rejects_global_collapse_matching_shortcut(isolated_config):
    config.load_config()
    values = build_settings_values(
        **_base_settings_kwargs(
            hotkey_collapse="Ctrl+Shift+M",
            shortcut_collapse="Ctrl+Shift+M",
        )
    )
    assert (
        apply_settings_values(values)
        == "Global hotkeys cannot match an in-app shortcut."
    )


def test_hotkey_collapse_config_defaults(isolated_config):
    cfg = config.load_config()
    assert cfg["hotkey_collapse"] == DEFAULT_HOTKEY_COLLAPSE


def test_apply_settings_shortcut_and_clipboard_round_trip(isolated_config):
    config.load_config()
    values = build_settings_values(
        **_base_settings_kwargs(
            shortcut_collapse="Ctrl+Alt+K",
            shortcut_hide_tray="F11",
            shortcut_private="Ctrl+Shift+U",
            auto_copy_clipboard=False,
        )
    )
    assert apply_settings_values(values) is None

    cfg = config.load_config()
    assert cfg["shortcut_collapse"] == "Ctrl+Alt+K"
    assert cfg["shortcut_hide_tray"] == "F11"
    assert cfg["shortcut_private"] == "Ctrl+Shift+U"
    assert cfg["auto_copy_clipboard"] is False
    assert shortcuts_equal("Ctrl+Alt+K", "Ctrl+Alt+K")
    assert not shortcuts_equal("Ctrl+Alt+K", "F11")
