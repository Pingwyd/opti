"""Tests for window enumeration and inject target resolution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import config
import window_service as ws
from window_service import InjectTargetPreference, WindowService


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    return config_path


@pytest.mark.parametrize(
    ("title", "process_name", "expected"),
    [
        ("ChatGPT — Google Chrome", "chrome.exe", False),
        ("1Password - Vault", "1Password.exe", True),
        ("My Notes", "notepad.exe", False),
    ],
)
def test_is_taskbar_window_respects_blocklist(title, process_name, expected):
    excluded = frozenset()
    with patch("window_service.is_windows", return_value=True):
        mock_gui = MagicMock()
        mock_gui.IsWindow.return_value = True
        mock_gui.IsWindowVisible.return_value = True
        mock_gui.GetWindow.return_value = 0
        mock_gui.GetWindowText.return_value = title
        mock_gui.GetWindowLong.side_effect = [0x10000000, 0]  # WS_VISIBLE, no toolwindow
        with patch.dict("sys.modules", {"win32gui": mock_gui, "win32con": MagicMock()}):
            with patch("window_service._process_name_for_hwnd", return_value=process_name):
                with patch("window_service.is_self_process", return_value=False):
                    result = ws.is_taskbar_window(100, excluded=excluded)
    if expected:
        assert result is False
    else:
        assert result is True


def test_enumerate_windows_empty_off_windows():
    with patch("window_service.is_windows", return_value=False):
        service = WindowService()
        assert service.enumerate_windows() == []


@patch("window_service.is_windows", return_value=True)
def test_enumerate_windows_collects_visible(_is_windows):
    captured: list[int] = []

    def enum_windows(callback, _lparam):
        for hwnd in (10, 20):
            callback(hwnd, 0)
        return True

    mock_gui = MagicMock()
    mock_gui.EnumWindows.side_effect = enum_windows
    with patch.dict("sys.modules", {"win32gui": mock_gui}):
        with patch(
            "window_service.is_taskbar_window",
            side_effect=lambda hwnd, excluded: hwnd == 10,
        ):
            with patch(
                "window_service._process_name_for_hwnd",
                side_effect=lambda hwnd: "notepad.exe" if hwnd == 10 else "",
            ):
                mock_gui.GetWindowText.side_effect = lambda hwnd: "Notepad" if hwnd == 10 else ""
                service = WindowService()
                windows = service.enumerate_windows()
    assert len(windows) == 1
    assert windows[0]["hwnd"] == 10
    assert windows[0]["title"] == "Notepad"


@patch("window_service.is_windows", return_value=True)
def test_find_best_for_process_prefers_foreground(_is_windows):
    service = WindowService()
    windows = [
        {"hwnd": 1, "title": "A", "process_name": "code.exe"},
        {"hwnd": 2, "title": "B", "process_name": "code.exe"},
    ]
    with patch.object(service, "enumerate_windows", return_value=windows):
        mock_gui = MagicMock()
        mock_gui.GetForegroundWindow.return_value = 2
        with patch.dict("sys.modules", {"win32gui": mock_gui}):
            match = service.find_best_for_process("Code.exe")
    assert match is not None
    assert match["hwnd"] == 2


@patch("window_service.is_windows", return_value=True)
def test_resolve_inject_target_project_process_first(_is_windows):
    service = WindowService()
    info = {"hwnd": 55, "title": "VS Code", "process_name": "Code.exe"}
    with patch.object(service, "find_best_for_process", return_value=info):
        with patch("window_service.is_target_valid", return_value=True):
            with patch("window_service.is_self_target", return_value=False):
                with patch("window_service.is_blocked_target", return_value=False):
                    pref = InjectTargetPreference(
                        mode="dynamic",
                        pinned_hwnd=None,
                        project_process="Code.exe",
                    )
                    target = service.resolve_inject_target(pref, own_hwnd=99)
    assert target["hwnd"] == 55


@patch("window_service.is_windows", return_value=True)
def test_resolve_inject_target_pinned_hwnd(_is_windows):
    service = WindowService()
    mock_gui = MagicMock()
    mock_gui.GetWindowText.return_value = "Notepad"
    with patch.dict("sys.modules", {"win32gui": mock_gui}):
        with patch("window_service.is_target_valid", return_value=True):
            with patch("window_service._process_name_for_hwnd", return_value="notepad.exe"):
                with patch("window_service.is_blocked_target", return_value=False):
                    pref = InjectTargetPreference(mode="pinned", pinned_hwnd=42)
                    target = service.resolve_inject_target(
                        pref, own_hwnd=None, refresh_dynamic=False
                    )
    assert target["hwnd"] == 42


@patch("window_service.is_windows", return_value=True)
def test_window_at_screen_point(_is_windows):
    service = WindowService()
    with patch("window_service._top_level_hwnd_from_point", return_value=77):
        mock_gui = MagicMock()
        mock_gui.GetWindowText.return_value = "Chrome"
        with patch.dict("sys.modules", {"win32gui": mock_gui}):
            with patch("window_service._process_name_for_hwnd", return_value="chrome.exe"):
                info = service.window_at_screen_point(100, 200)
    assert info is not None
    assert info["hwnd"] == 77


def test_inject_target_config_round_trip(isolated_config):
    config.load_config()
    assert config.get_inject_target_mode() == "dynamic"
    assert config.get_inject_pinned_hwnd() is None
    config.set_inject_target_mode("pinned")
    config.set_inject_pinned_hwnd(1234)
    assert config.get_inject_target_mode() == "pinned"
    assert config.get_inject_pinned_hwnd() == 1234
