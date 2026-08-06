"""Tests for auto-inject helpers and config."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

import config
import inject


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    return config_path


@pytest.mark.parametrize(
    ("title", "process_name", "expected"),
    [
        ("ChatGPT — Google Chrome", None, False),
        ("1Password - Vault", None, True),
        ("Bitwarden", "chrome.exe", True),
        (None, "KeePass.exe", True),
        ("My Notes", "notepad.exe", False),
        ("Dashlane Premium", None, True),
        ("LASTPASS", None, True),
    ],
)
def test_is_blocked_target(title, process_name, expected):
    assert inject.is_blocked_target(title, process_name) is expected


def test_is_target_valid_false_without_hwnd():
    assert inject.is_target_valid(None) is False
    assert inject.is_target_valid(0) is False


@patch("inject.is_windows", return_value=True)
def test_is_target_valid_uses_is_window(_is_windows):
    mock_gui = MagicMock()
    mock_gui.IsWindow.return_value = True
    with patch.dict("sys.modules", {"win32gui": mock_gui}):
        assert inject.is_target_valid(12345) is True
        mock_gui.IsWindow.assert_called_once_with(12345)


@patch("inject.is_windows", return_value=True)
def test_is_target_valid_false_when_window_closed(_is_windows):
    mock_gui = MagicMock()
    mock_gui.IsWindow.return_value = False
    with patch.dict("sys.modules", {"win32gui": mock_gui}):
        assert inject.is_target_valid(999) is False


def test_can_inject_target_requires_valid_non_blocked():
    assert inject.can_inject_target(None) is False
    assert inject.can_inject_target({}) is False

    with patch("inject.is_target_valid", return_value=True):
        assert inject.can_inject_target({"hwnd": 1, "title": "VS Code"}) is True
        assert (
            inject.can_inject_target(
                {"hwnd": 1, "title": "Bitwarden", "process_name": "Bitwarden.exe"}
            )
            is False
        )


@patch("inject.is_windows", return_value=False)
def test_record_foreground_target_noop_off_windows(_is_windows):
    assert inject.record_foreground_target() == {}


@patch("inject.is_windows", return_value=True)
def test_record_foreground_target_captures_hwnd_and_title(_is_windows):
    mock_gui = MagicMock()
    mock_gui.GetForegroundWindow.return_value = 42
    mock_gui.GetWindowText.return_value = "Notepad"
    with patch.dict("sys.modules", {"win32gui": mock_gui}):
        with patch("inject._process_name_for_hwnd", return_value="notepad.exe"):
            target = inject.record_foreground_target()
    assert target == {"hwnd": 42, "title": "Notepad", "process_name": "notepad.exe"}


@patch("inject.is_windows", return_value=False)
def test_inject_via_paste_noop_off_windows(_is_windows):
    ok, message = inject.inject_via_paste(1, "hello")
    assert ok is False
    assert "Windows" in message


def test_auto_inject_config_defaults(isolated_config):
    cfg = config.load_config()
    assert cfg["auto_inject_enabled"] is False
    assert config.get_auto_inject_enabled() is False


def test_auto_inject_config_round_trip(isolated_config):
    config.load_config()
    config.set_auto_inject_enabled(True)
    assert config.get_auto_inject_enabled() is True
    cfg = config.load_config()
    assert cfg["auto_inject_enabled"] is True

    config.set_auto_inject_enabled(False)
    assert config.get_auto_inject_enabled() is False


def test_apply_settings_persists_auto_inject(isolated_config):
    from settings_ui import apply_settings_values, build_settings_values

    config.load_config()
    values = build_settings_values(
        provider="gemini",
        api_key_input="",
        hotkey="Ctrl+Shift+Space",
        hotkey_collapse=config.DEFAULT_HOTKEY_COLLAPSE,
        model="gemini-3.5-flash",
        model_fast="gemini-3.1-flash-lite",
        mode="thorough",
        persist_draft=True,
        save_history=True,
        exclude_sensitive=False,
        history_limit=50,
        start_with_windows=False,
        shortcut_collapse=config.DEFAULT_SHORTCUT_COLLAPSE,
        shortcut_hide_tray=config.DEFAULT_SHORTCUT_HIDE_TRAY,
        shortcut_private=config.DEFAULT_SHORTCUT_PRIVATE,
        auto_copy_clipboard=True,
        auto_inject_enabled=True,
    )
    assert apply_settings_values(values) is None
    assert config.get_auto_inject_enabled() is True
