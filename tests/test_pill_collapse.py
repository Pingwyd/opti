"""Tests for pill collapse config persistence and global collapse toggle."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

import config
from popup import PopupController, collapse_global_action


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point config at a temp file so tests never touch the real config.json."""
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    return config_path


def test_collapse_global_action_state_machine():
    assert collapse_global_action(is_visible=False, is_collapsed=False) == "show_chip"
    assert collapse_global_action(is_visible=False, is_collapsed=True) == "show_chip"
    assert collapse_global_action(is_visible=True, is_collapsed=True) == "expand"
    assert collapse_global_action(is_visible=True, is_collapsed=False) == "collapse"


def test_toggle_collapse_global_from_hidden_shows_chip(qapp, isolated_config, monkeypatch):
    from popup import PopupController

    monkeypatch.setattr("popup.has_api_key", lambda: True)

    controller = PopupController()
    window = controller.create_window()
    assert not window.isVisible()

    window.toggle_collapse_global()
    assert window.isVisible()
    assert window.is_pill_collapsed()


def test_toggle_popup_hides_when_visible(qapp, isolated_config, monkeypatch):
    from popup import PopupController

    monkeypatch.setattr("popup.has_api_key", lambda: True)

    controller = PopupController()
    window = controller.create_window()
    window.show_popup(force_expand=True)
    assert window.isVisible()

    window.toggle_popup()
    assert not window.isVisible()
    assert not window._visible


def test_expand_uses_live_chip_position_not_stale_window_position(
    qapp, isolated_config, monkeypatch
):
    """Expanding after dragging the chip should keep the dragged coordinates."""
    from popup import PopupController

    monkeypatch.setattr("popup.has_api_key", lambda: True)

    controller = PopupController()
    window = controller.create_window()
    window._visible = True

    config.load_config()
    config.set_window_position(100, 200)

    window.move(100, 200)
    window.collapse()
    assert window.is_pill_collapsed()

    window.move(450, 380)
    window.expand()

    assert not window.is_pill_collapsed()
    assert window.x() == 450
    assert window.y() == 380
    assert config.get_window_position() == (450, 380)


def test_pill_collapsed_defaults_false(isolated_config):
    cfg = config.load_config()
    assert cfg["pill_collapsed"] is False


def test_pill_collapsed_round_trip(isolated_config):
    config.load_config()
    config.set_pill_collapsed(True)
    assert config.get_pill_collapsed() is True
    assert config.load_config()["pill_collapsed"] is True
    config.set_pill_collapsed(False)
    assert config.get_pill_collapsed() is False


def test_window_position_round_trip(isolated_config):
    config.load_config()
    config.set_window_position(120, 340)
    assert config.get_window_position() == (120, 340)
    cfg = config.load_config()
    assert cfg["window_x"] == 120
    assert cfg["window_y"] == 340


def test_window_position_invalid_returns_none(isolated_config):
    isolated_config.write_text('{"window_x": "bad", "window_y": 10}', encoding="utf-8")
    assert config.get_window_position() == (None, None)


def test_chip_position_round_trip(isolated_config):
    config.load_config()
    config.set_chip_position(80, 160)
    assert config.get_chip_position() == (80, 160)
    cfg = config.load_config()
    assert cfg["window_x"] == 80
    assert cfg["window_y"] == 160


def test_window_position_migrates_from_chip_only(isolated_config):
    isolated_config.write_text('{"chip_x": 150, "chip_y": 250}', encoding="utf-8")
    assert config.get_window_position() == (150, 250)
    cfg = config.load_config()
    assert cfg["window_x"] == 150
    assert cfg["window_y"] == 250


def test_reopen_collapsed_uses_unified_expanded_position(
    qapp, isolated_config, monkeypatch
):
    """Collapsed reopen should use the last unified position, not a separate chip store."""
    from popup import PopupController

    monkeypatch.setattr("popup.has_api_key", lambda: True)

    config.load_config()
    config.set_window_position(300, 200)
    config.set_pill_collapsed(True)

    controller = PopupController()
    window = controller.create_window()
    window.show_popup(force_collapse=True)

    assert window.is_pill_collapsed()
    assert window.x() == 300
    assert window.y() == 200


def test_drag_chip_then_expand_keeps_unified_position(
    qapp, isolated_config, monkeypatch
):
    """Dragging the chip updates the unified position used on expand."""
    from popup import PopupController

    monkeypatch.setattr("popup.has_api_key", lambda: True)

    controller = PopupController()
    window = controller.create_window()
    window._visible = True

    config.load_config()
    config.set_window_position(100, 200)

    window.move(100, 200)
    window.collapse()
    window.move(500, 400)
    window._persist_window_position(force=True)
    window.expand()

    assert window.x() == 500
    assert window.y() == 400
    assert config.get_window_position() == (500, 400)


def test_chip_position_falls_back_to_window_position(isolated_config):
    config.load_config()
    config.set_window_position(200, 300)
    assert config.get_chip_position() == (200, 300)


def test_clamp_window_position_keeps_window_on_screen():
    x, y = config.clamp_window_position(
        5000,
        5000,
        width=400,
        height=80,
        screen_x=0,
        screen_y=0,
        screen_width=1920,
        screen_height=1080,
    )
    assert x < 1920
    assert y < 1080
    assert x + 400 > 24
    assert y + 80 > 24


def test_clamp_window_position_preserves_in_bounds_coords():
    x, y = config.clamp_window_position(
        100,
        200,
        width=400,
        height=80,
        screen_x=0,
        screen_y=0,
        screen_width=1920,
        screen_height=1080,
    )
    assert (x, y) == (100, 200)
