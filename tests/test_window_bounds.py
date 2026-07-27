"""Tests for window boundary validation and rescue logic."""

from __future__ import annotations

import pytest

import config

PRIMARY = (0, 0, 1920, 1080)
SECONDARY = (1920, 0, 1920, 1080)
DUAL_MONITORS = [PRIMARY, SECONDARY]


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point config at a temp file so tests never touch the real config.json."""
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    return config_path
SECONDARY = (1920, 0, 1920, 1080)
DUAL_MONITORS = [PRIMARY, SECONDARY]


def test_window_intersects_any_screen_true_when_on_primary():
    assert config.window_intersects_any_screen(100, 200, 400, 80, DUAL_MONITORS)


def test_window_intersects_any_screen_false_for_ghost_position():
    assert not config.window_intersects_any_screen(5000, 5000, 400, 80, DUAL_MONITORS)


def test_screen_for_window_uses_center_point():
    screen = config.screen_for_window(2100, 100, 400, 80, DUAL_MONITORS)
    assert screen == SECONDARY


def test_screen_for_window_falls_back_to_largest_intersection():
    # Center is off-screen but the window still straddles the primary monitor edge.
    screen = config.screen_for_window(-50, 100, 400, 80, DUAL_MONITORS)
    assert screen == PRIMARY


def test_screen_for_window_returns_none_when_fully_off_screen():
    assert config.screen_for_window(5000, 5000, 400, 80, DUAL_MONITORS) is None


def test_validate_window_position_ghost_centers_on_primary():
    x, y, rescued = config.validate_window_position(
        5000,
        5000,
        400,
        80,
        DUAL_MONITORS,
    )
    assert rescued is True
    assert config.window_intersects_any_screen(x, y, 400, 80, DUAL_MONITORS)
    assert PRIMARY[0] <= x < PRIMARY[0] + PRIMARY[2]
    assert PRIMARY[1] <= y < PRIMARY[1] + PRIMARY[3]


def test_validate_window_position_clamps_off_right_edge():
    x, y, rescued = config.validate_window_position(
        1900,
        200,
        400,
        80,
        [PRIMARY],
    )
    assert config.window_intersects_any_screen(x, y, 400, 80, [PRIMARY])
    assert x == 1896
    assert rescued is True


def test_validate_window_position_preserves_in_bounds_coords():
    x, y, rescued = config.validate_window_position(
        100,
        200,
        400,
        80,
        [PRIMARY],
    )
    assert (x, y) == (100, 200)
    assert rescued is False


def test_center_window_on_screen_is_within_bounds():
    x, y = config.center_window_on_screen(400, 80, *PRIMARY)
    assert config.window_intersects_any_screen(x, y, 400, 80, [PRIMARY])


def test_unified_position_shared_across_states(isolated_config):
    """Expanded and collapsed states read the same canonical window_x/y."""
    config.load_config()
    config.set_window_position(300, 200)
    assert config.get_window_position() == (300, 200)
    assert config.get_chip_position() == (300, 200)


def test_clamp_window_position_centers_when_window_wider_than_screen():
    x, y = config.clamp_window_position(
        0,
        0,
        width=37,
        height=10,
        screen_x=0,
        screen_y=0,
        screen_width=10,
        screen_height=8,
        margin=24,
    )
    assert x == (10 - 37) // 2
    assert y == (8 - 10) // 2
