"""
Windows auto-inject: record foreground window and paste into it on user confirm.

No-op on non-Windows platforms.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any, TypedDict

import pyperclip

log = logging.getLogger(__name__)

BLOCKED_APP_NAMES: tuple[str, ...] = (
    "1password",
    "bitwarden",
    "keepass",
    "lastpass",
    "dashlane",
)


class ForegroundTarget(TypedDict, total=False):
    hwnd: int
    title: str
    process_name: str


def is_windows() -> bool:
    return sys.platform == "win32"


def is_blocked_target(title: str | None, process_name: str | None) -> bool:
    """Best-effort blocklist for password managers and similar apps."""
    haystacks: list[str] = []
    if title:
        haystacks.append(title.lower())
    if process_name:
        haystacks.append(process_name.lower())
    for blocked in BLOCKED_APP_NAMES:
        for hay in haystacks:
            if blocked in hay:
                return True
    return False


def is_target_valid(hwnd: int | None) -> bool:
    """Return True when hwnd still refers to an open window."""
    if not hwnd or not is_windows():
        return False
    try:
        import win32gui

        return bool(win32gui.IsWindow(int(hwnd)))
    except Exception:
        log.debug("is_target_valid failed for hwnd=%s", hwnd, exc_info=True)
        return False


def _process_name_for_hwnd(hwnd: int) -> str | None:
    if not is_windows():
        return None
    try:
        import ctypes
        import win32process
        from ctypes import wintypes

        _, pid = win32process.GetWindowThreadProcessId(int(hwnd))
        if not pid:
            return None

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            size = wintypes.DWORD(32768)
            buf = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value)
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        log.debug("Failed to resolve process name for hwnd=%s", hwnd, exc_info=True)
    return None


def record_foreground_target() -> ForegroundTarget:
    """
    Capture the currently focused window before Opti steals focus.

    Returns an empty dict on non-Windows or when capture fails.
    """
    if not is_windows():
        return {}

    try:
        import win32gui

        hwnd = int(win32gui.GetForegroundWindow())
        if not hwnd:
            return {}
        title = (win32gui.GetWindowText(hwnd) or "").strip()
        process_name = _process_name_for_hwnd(hwnd)
        target: ForegroundTarget = {"hwnd": hwnd, "title": title or "Unknown window"}
        if process_name:
            target["process_name"] = process_name
        return target
    except Exception:
        log.warning("record_foreground_target failed", exc_info=True)
        return {}


def can_inject_target(target: ForegroundTarget | None) -> bool:
    """True when auto-inject UI should offer injection for this recorded target."""
    if not target:
        return False
    hwnd = target.get("hwnd")
    if not is_target_valid(hwnd):
        return False
    title = target.get("title")
    process_name = target.get("process_name")
    return not is_blocked_target(title, process_name)


def _send_ctrl_v() -> None:
    from pynput.keyboard import Controller, Key

    kb = Controller()
    with kb.pressed(Key.ctrl):
        kb.press("v")
        kb.release("v")


def inject_via_paste(hwnd: int, text: str) -> tuple[bool, str]:
    """
    Restore focus to hwnd and simulate Ctrl+V with clipboard content.

    Returns (success, message).
    """
    if not is_windows():
        return False, "Auto-Inject is only available on Windows."

    if not is_target_valid(hwnd):
        return False, "Target window is no longer available. Use clipboard instead."

    if not (text or "").strip():
        return False, "Nothing to inject."

    try:
        import win32con
        import win32gui

        hwnd = int(hwnd)
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            log.debug("SetForegroundWindow failed; continuing", exc_info=True)

        time.sleep(0.15)

        try:
            current = pyperclip.paste()
            if current != text:
                pyperclip.copy(text)
        except Exception:
            log.warning("Clipboard set before inject failed", exc_info=True)
            return False, "Could not set clipboard for paste."

        _send_ctrl_v()
        return True, "Pasted into target window."
    except Exception as exc:
        log.exception("inject_via_paste failed")
        return False, f"Inject failed: {exc}"
