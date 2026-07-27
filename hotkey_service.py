"""
Global hotkey listener via pynput.

Runs in a background thread; activation callbacks must be thread-safe
(e.g. marshal to the Qt main thread via a signal).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Mapping
from typing import Any

from config import DEFAULT_HOTKEY, normalize_hotkey_string

log = logging.getLogger(__name__)

DEFAULT_PYNPUT_COMBO = "<ctrl>+<shift>+<space>"

_PYNPUT_KEY_ALIASES: dict[str, str] = {
    "ctrl": "<ctrl>",
    "control": "<ctrl>",
    "alt": "<alt>",
    "shift": "<shift>",
    "win": "<cmd>",
    "meta": "<cmd>",
    "cmd": "<cmd>",
    "super": "<cmd>",
    "space": "<space>",
    "esc": "<esc>",
    "escape": "<esc>",
    "enter": "<enter>",
    "return": "<enter>",
    "tab": "<tab>",
}


def parse_hotkey_to_pynput(hotkey: str) -> str:
    """
    Convert a config hotkey string (QKeySequence portable or legacy lowercase)
    to a pynput GlobalHotKeys combo string.
    """
    normalized = normalize_hotkey_string(hotkey, DEFAULT_HOTKEY)
    parts = [p.strip().lower() for p in normalized.split("+") if p.strip()]
    combo: list[str] = []
    for part in parts:
        if part in _PYNPUT_KEY_ALIASES:
            combo.append(_PYNPUT_KEY_ALIASES[part])
        elif len(part) == 1:
            combo.append(part)
        else:
            combo.append(f"<{part}>")
    return "+".join(combo) if combo else DEFAULT_PYNPUT_COMBO


HotkeyBindings = Mapping[str, Callable[[], None]]


class GlobalHotkeyService:
    """Wrap pynput GlobalHotKeys with start/stop/restart lifecycle."""

    def __init__(self, on_activate: Callable[[], None] | None = None) -> None:
        self._default_callback = on_activate
        self._listener: Any | None = None
        self._lock = threading.Lock()

    def start(self, hotkey_spec: str | HotkeyBindings, on_activate: Callable[[], None] | None = None) -> None:
        """
        Start listening for one or more hotkeys, stopping any prior listener.

        When `hotkey_spec` is a mapping, keys are config hotkey strings and values
        are callbacks. When it is a string, `on_activate` (or the constructor
        callback) is used for that single binding.
        """
        if isinstance(hotkey_spec, str):
            callback = on_activate or self._default_callback
            if callback is None:
                raise ValueError("on_activate is required for a single hotkey binding")
            bindings = {hotkey_spec: callback}
        else:
            bindings = dict(hotkey_spec)

        with self._lock:
            self._stop_unlocked()
            from pynput.keyboard import GlobalHotKeys

            hotkeys: dict[str, Callable[[], None]] = {}
            for spec, callback in bindings.items():
                combo = parse_hotkey_to_pynput(spec)

                def _safe_activate(cb: Callable[[], None] = callback) -> None:
                    try:
                        cb()
                    except Exception:
                        log.exception("Hotkey callback failed")

                hotkeys[combo] = _safe_activate

            listener = GlobalHotKeys(hotkeys)
            listener.daemon = True  # type: ignore[attr-defined]
            listener.start()
            self._listener = listener
            log.info("Global hotkey listener started (%s)", ", ".join(sorted(hotkeys.keys())))

    def stop(self) -> None:
        """Stop the listener if running."""
        with self._lock:
            self._stop_unlocked()

    def restart(self, hotkey_spec: str | HotkeyBindings, on_activate: Callable[[], None] | None = None) -> None:
        """Replace the active hotkey bindings."""
        self.start(hotkey_spec, on_activate=on_activate)

    def _stop_unlocked(self) -> None:
        listener = self._listener
        if listener is None:
            return
        try:
            listener.stop()
            log.info("Global hotkey listener stopped")
        except Exception:
            log.warning("Hotkey listener stop failed", exc_info=True)
        finally:
            self._listener = None
