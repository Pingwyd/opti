"""Tests for global hotkey string parsing and listener lifecycle."""

from __future__ import annotations

import pytest

from config import (
    DEFAULT_HOTKEY,
    DEFAULT_HOTKEY_COLLAPSE,
    get_hotkey,
    get_hotkey_collapse,
    normalize_hotkey_string,
    set_hotkey,
    set_hotkey_collapse,
)
from hotkey_service import GlobalHotkeyService, parse_hotkey_to_pynput


def test_parse_hotkey_modifiers_and_space():
    assert parse_hotkey_to_pynput("ctrl+shift+space") == "<ctrl>+<shift>+<space>"


def test_parse_hotkey_single_letter():
    assert parse_hotkey_to_pynput("ctrl+shift+p") == "<ctrl>+<shift>+p"


def test_parse_hotkey_aliases():
    assert parse_hotkey_to_pynput("control+alt+tab") == "<ctrl>+<alt>+<tab>"


def test_parse_hotkey_function_key():
    assert parse_hotkey_to_pynput("ctrl+f5") == "<ctrl>+<f5>"


def test_parse_hotkey_empty_defaults():
    assert parse_hotkey_to_pynput("") == "<ctrl>+<shift>+<space>"


def test_parse_hotkey_qkeysequence_format():
    assert parse_hotkey_to_pynput("Ctrl+Shift+Space") == "<ctrl>+<shift>+<space>"


def test_normalize_hotkey_string_round_trip():
    assert normalize_hotkey_string("ctrl+shift+space") == DEFAULT_HOTKEY
    assert normalize_hotkey_string("Ctrl+Alt+K") == "Ctrl+Alt+K"


def test_hotkey_config_round_trip(isolated_config):
    import config

    config.load_config()
    set_hotkey("Ctrl+Shift+P")
    assert get_hotkey() == "Ctrl+Shift+P"
    assert parse_hotkey_to_pynput(get_hotkey()) == "<ctrl>+<shift>+p"


def test_hotkey_collapse_config_round_trip(isolated_config):
    import config

    config.load_config()
    set_hotkey_collapse("Ctrl+Alt+C")
    assert get_hotkey_collapse() == "Ctrl+Alt+C"
    assert parse_hotkey_to_pynput(get_hotkey_collapse()) == "<ctrl>+<alt>+c"


def test_global_hotkey_service_multiple_bindings(monkeypatch):
    created: list[dict] = []
    calls: list[str] = []

    class FakeGlobalHotKeys:
        def __init__(self, hotkeys):
            created.append(hotkeys)
            self.daemon = False

        def start(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr("pynput.keyboard.GlobalHotKeys", FakeGlobalHotKeys)

    service = GlobalHotkeyService()
    service.start(
        {
            "Ctrl+Shift+Space": lambda: calls.append("open"),
            "Ctrl+Alt+M": lambda: calls.append("collapse"),
        }
    )
    assert set(created[0].keys()) == {"<ctrl>+<shift>+<space>", "<ctrl>+<alt>+m"}
    created[0]["<ctrl>+<shift>+<space>"]()
    created[0]["<ctrl>+<alt>+m"]()
    assert calls == ["open", "collapse"]


def test_global_hotkey_service_start_stop(monkeypatch):
    created: list[dict] = []

    class FakeGlobalHotKeys:
        def __init__(self, hotkeys):
            created.append(hotkeys)
            self.daemon = False

        def start(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr("pynput.keyboard.GlobalHotKeys", FakeGlobalHotKeys)

    service = GlobalHotkeyService(lambda: None)
    service.start("Ctrl+Shift+Space")
    assert list(created[0].keys()) == ["<ctrl>+<shift>+<space>"]
    assert service._listener is not None

    service.stop()
    assert service._listener is None


def test_global_hotkey_service_restart(monkeypatch):
    instances: list[object] = []

    class FakeGlobalHotKeys:
        def __init__(self, hotkeys):
            self.hotkeys = hotkeys
            self.daemon = False
            instances.append(self)

        def start(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr("pynput.keyboard.GlobalHotKeys", FakeGlobalHotKeys)

    service = GlobalHotkeyService(lambda: None)
    service.start("Ctrl+Shift+Space")
    service.restart("Ctrl+Shift+P")
    assert len(instances) == 2
    assert list(instances[1].hotkeys.keys()) == ["<ctrl>+<shift>+p"]


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    import config

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    return config_path
