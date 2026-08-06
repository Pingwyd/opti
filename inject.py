"""
Windows auto-inject: record foreground window and paste into it on user confirm.

No-op on non-Windows platforms.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Iterable
from typing import TypedDict

import pyperclip

log = logging.getLogger(__name__)

BLOCKED_APP_NAMES: tuple[str, ...] = (
    "1password",
    "bitwarden",
    "keepass",
    "lastpass",
    "dashlane",
)

_SELF_PROCESS_NAMES: frozenset[str] = frozenset(
    {
        "python.exe",
        "pythonw.exe",
        "opti.exe",
        "metaprompt.exe",
    }
)

FOCUS_SETTLE_SECONDS = 0.2
INJECT_DEFER_MS = 200


class ForegroundTarget(TypedDict, total=False):
    hwnd: int
    title: str
    process_name: str


def is_windows() -> bool:
    return sys.platform == "win32"


def is_self_process(process_name: str | None) -> bool:
    if not process_name:
        return False
    return process_name.lower() in _SELF_PROCESS_NAMES


def is_self_target(
    target: ForegroundTarget | None,
    *,
    own_hwnd: int | None = None,
) -> bool:
    """True when the target is this app (inject would paste into Opti itself)."""
    if not target:
        return False
    hwnd = target.get("hwnd")
    if own_hwnd is not None and hwnd is not None and int(hwnd) == int(own_hwnd):
        return True
    return is_self_process(target.get("process_name"))


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


def _normalize_exclude_hwnds(exclude_hwnds: Iterable[int] | None) -> frozenset[int]:
    if not exclude_hwnds:
        return frozenset()
    return frozenset(int(h) for h in exclude_hwnds if h)


def record_foreground_target(
    *,
    exclude_hwnds: Iterable[int] | None = None,
) -> ForegroundTarget:
    """
    Capture the currently focused window before Opti steals focus.

    Returns an empty dict on non-Windows, when capture fails, or when the
    foreground window is Opti itself.
    """
    if not is_windows():
        return {}

    excluded = _normalize_exclude_hwnds(exclude_hwnds)

    try:
        import win32gui

        hwnd = int(win32gui.GetForegroundWindow())
        if not hwnd:
            return {}
        if hwnd in excluded:
            log.debug("inject capture skipped excluded hwnd=%s", hwnd)
            return {}
        title = (win32gui.GetWindowText(hwnd) or "").strip()
        process_name = _process_name_for_hwnd(hwnd)
        if is_self_process(process_name):
            log.debug("inject capture skipped self process=%s hwnd=%s", process_name, hwnd)
            return {}
        target: ForegroundTarget = {"hwnd": hwnd, "title": title or "Unknown window"}
        if process_name:
            target["process_name"] = process_name
        log.info(
            "inject capture: hwnd=%s title=%r process=%r",
            hwnd,
            target.get("title"),
            process_name,
        )
        return target
    except Exception:
        log.warning("record_foreground_target failed", exc_info=True)
        return {}


def can_inject_target(
    target: ForegroundTarget | None,
    *,
    own_hwnd: int | None = None,
) -> bool:
    """True when auto-inject UI should offer injection for this recorded target."""
    if not target:
        return False
    hwnd = target.get("hwnd")
    if not is_target_valid(hwnd):
        return False
    if is_self_target(target, own_hwnd=own_hwnd):
        return False
    title = target.get("title")
    process_name = target.get("process_name")
    return not is_blocked_target(title, process_name)


def _force_foreground(hwnd: int) -> bool:
    """Best-effort restore focus on Windows (handles focus-stealing restrictions)."""
    if not is_windows():
        return False
    try:
        import win32con
        import win32gui
        import win32process

        hwnd = int(hwnd)
        if win32gui.GetForegroundWindow() == hwnd:
            return True

        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        fg_hwnd = win32gui.GetForegroundWindow()
        fg_thread, _ = win32process.GetWindowThreadProcessId(fg_hwnd)
        target_thread, _ = win32process.GetWindowThreadProcessId(hwnd)
        attached = False
        if fg_thread and target_thread and fg_thread != target_thread:
            win32process.AttachThreadInput(fg_thread, target_thread, True)
            attached = True
        try:
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
        finally:
            if attached:
                win32process.AttachThreadInput(fg_thread, target_thread, False)

        ok = win32gui.GetForegroundWindow() == hwnd
        if not ok:
            log.warning(
                "inject focus restore failed: target=%s foreground=%s",
                hwnd,
                win32gui.GetForegroundWindow(),
            )
        return ok
    except Exception:
        log.warning("_force_foreground failed for hwnd=%s", hwnd, exc_info=True)
        return False


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
        import win32gui

        hwnd = int(hwnd)
        fg_before = win32gui.GetForegroundWindow()
        log.info("inject paste: target=%s foreground_before=%s", hwnd, fg_before)

        focused = _force_foreground(hwnd)
        time.sleep(FOCUS_SETTLE_SECONDS)

        fg_after = win32gui.GetForegroundWindow()
        log.info(
            "inject paste: target=%s foreground_after=%s focused=%s",
            hwnd,
            fg_after,
            focused,
        )

        try:
            pyperclip.copy(text)
        except Exception:
            log.warning("Clipboard set before inject failed", exc_info=True)
            return False, "Could not set clipboard for paste."

        _send_ctrl_v()
        return True, "Pasted into target window."
    except Exception as exc:
        log.exception("inject_via_paste failed")
        return False, f"Inject failed: {exc}"
