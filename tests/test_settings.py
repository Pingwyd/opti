"""Tests for settings persistence and dialog construction."""

from __future__ import annotations

import time

import pytest
from PyQt6.QtWidgets import QApplication, QPushButton

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
from brand import SETUP_TITLE, SETTINGS_TITLE
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
    vault_path = tmp_path / "vault.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr("vault.VAULT_PATH", vault_path)
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
        "start_minimized_to_tray": True,
        "check_updates_on_launch": False,
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
    assert dlg.windowTitle() == SETTINGS_TITLE

    first_run = SettingsDialog(first_run=True)
    assert first_run.windowTitle() == SETUP_TITLE


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


def test_startup_config_defaults(isolated_config):
    cfg = config.load_config()
    assert cfg["start_minimized_to_tray"] is True
    assert cfg["check_updates_on_launch"] is False


def test_apply_settings_startup_options_round_trip(isolated_config):
    config.load_config()
    values = build_settings_values(
        **_base_settings_kwargs(
            start_minimized_to_tray=False,
            check_updates_on_launch=True,
        )
    )
    assert apply_settings_values(values) is None

    cfg = config.load_config()
    assert cfg["start_minimized_to_tray"] is False
    assert cfg["check_updates_on_launch"] is True
    assert config.get_start_minimized_to_tray() is False
    assert config.get_check_updates_on_launch() is True


def test_settings_dialog_immediate_apply_footer(qapp, isolated_config):
    config.load_config()
    dlg = SettingsDialog()
    assert not hasattr(dlg, "_save_btn")
    close_btns = dlg.findChildren(QPushButton, "footerCloseBtn")
    assert len(close_btns) == 1
    assert close_btns[0].text() == "Close"
    dlg.close()


def test_settings_voice_toggle_immediate_apply(qapp, isolated_config):
    config.load_config()
    dlg = SettingsDialog()
    assert not dlg._voice_enabled_toggle.isChecked()
    dlg._voice_enabled_toggle.setChecked(True)
    qapp.processEvents()
    assert config.load_config()["voice_enabled"] is True
    dlg._voice_enabled_toggle.setChecked(False)
    qapp.processEvents()
    from PyQt6.QtTest import QTest

    QTest.qWait(100)
    qapp.processEvents()
    assert config.load_config()["voice_enabled"] is False
    dlg.close()


def test_debounced_config_writer_coalesces_writes(qapp, isolated_config, monkeypatch):
    from settings_ui import DebouncedConfigWriter

    writes: list[dict] = []

    def fake_update(patch):
        writes.append(dict(patch))
        return patch

    monkeypatch.setattr("settings_ui.update_config", fake_update)
    writer = DebouncedConfigWriter(50, qapp)
    writer.write({"model": "a"}, immediate=False)
    writer.write({"model": "b"}, immediate=False)
    writer.write({"model_fast": "c"}, immediate=False)
    assert len(writes) == 0

    deadline = time.time() + 1.0
    while not writes and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.02)

    assert len(writes) == 1
    assert writes[0] == {"model": "b", "model_fast": "c"}
    writer.shutdown()


def test_compute_shortcut_conflicts_detects_duplicates():
    from settings_ui import compute_shortcut_conflicts

    conflicts = compute_shortcut_conflicts(
        "Ctrl+Alt+,",
        "Ctrl+Alt+,",
        "Ctrl+Alt+]",
        "Esc",
        "Ctrl+Shift+P",
        "Ctrl+T",
        "Ctrl+Shift+T",
        "Ctrl+Space",
    )
    assert conflicts["hotkey"] is True
    assert conflicts["hotkey_collapse"] is True
    assert conflicts["shortcut_collapse"] is False


def test_setting_row_height_scales_with_font(qapp):
    from PyQt6.QtGui import QFont
    from widgets import SettingRow

    small = SettingRow("Label")
    small.label_widget().setFont(QFont("Segoe UI", 10))
    small._recompute_height()
    small_h = small.minimumHeight()

    large = SettingRow("Label")
    large.label_widget().setFont(QFont("Segoe UI", 16))
    large._recompute_height()
    large_h = large.minimumHeight()

    assert large_h > small_h


def test_project_color_is_stable_across_calls():
    from ui_theme import project_color

    a = project_color("MetaPrompt")
    b = project_color("MetaPrompt")
    assert a == b
    assert a != project_color("")


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
