"""
Windows taskbar window enumeration and target resolution for inject.

Pure win32 backend — no PyQt imports. UI layers convert HWND icons separately.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TypedDict

from inject import (
    ForegroundTarget,
    is_blocked_target,
    is_self_process,
    is_self_target,
    is_target_valid,
    record_foreground_target,
)

log = logging.getLogger(__name__)

INJECT_TARGET_DYNAMIC = "dynamic"
INJECT_TARGET_PINNED = "pinned"


class WindowInfo(TypedDict):
    hwnd: int
    title: str
    process_name: str


@dataclass(frozen=True)
class InjectTargetPreference:
    """User/project preference for how inject targets are chosen."""

    mode: str = INJECT_TARGET_DYNAMIC
    pinned_hwnd: int | None = None
    project_process: str | None = None


def is_windows() -> bool:
    return sys.platform == "win32"


def _normalize_exclude_hwnds(exclude_hwnds: Iterable[int] | None) -> frozenset[int]:
    if not exclude_hwnds:
        return frozenset()
    return frozenset(int(h) for h in exclude_hwnds if h)


def _process_name_for_hwnd(hwnd: int) -> str:
    if not is_windows():
        return ""
    try:
        import ctypes
        import win32process
        from ctypes import wintypes

        _, pid = win32process.GetWindowThreadProcessId(int(hwnd))
        if not pid:
            return ""

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(32768)
            buf = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value)
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        log.debug("process name lookup failed hwnd=%s", hwnd, exc_info=True)
    return ""


def is_taskbar_window(hwnd: int, *, excluded: frozenset[int]) -> bool:
    """
    True for visible top-level windows that typically appear on the taskbar.

    Filters tool windows, owned/minimized helpers, empty titles, and excluded HWNDs.
    """
    if not is_windows() or not hwnd:
        return False
    if int(hwnd) in excluded:
        return False
    try:
        import win32con
        import win32gui

        hwnd = int(hwnd)
        if not win32gui.IsWindow(hwnd):
            return False
        if not win32gui.IsWindowVisible(hwnd):
            return False
        if win32gui.GetWindow(hwnd, win32con.GW_OWNER):
            return False

        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        if not (style & win32con.WS_VISIBLE):
            return False

        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex_style & win32con.WS_EX_TOOLWINDOW:
            if not (ex_style & win32con.WS_EX_APPWINDOW):
                return False

        title = (win32gui.GetWindowText(hwnd) or "").strip()
        if not title:
            return False

        process_name = _process_name_for_hwnd(hwnd)
        if is_self_process(process_name):
            return False
        if is_blocked_target(title, process_name):
            return False
        return True
    except Exception:
        log.debug("is_taskbar_window failed hwnd=%s", hwnd, exc_info=True)
        return False


def _top_level_hwnd_from_point(x: int, y: int, *, excluded: frozenset[int]) -> int | None:
    if not is_windows():
        return None
    try:
        import win32gui

        hwnd = int(win32gui.WindowFromPoint((int(x), int(y))))
        while hwnd:
            if is_taskbar_window(hwnd, excluded=excluded):
                return hwnd
            parent = win32gui.GetParent(hwnd)
            if not parent:
                break
            hwnd = int(parent)
        return None
    except Exception:
        log.debug("WindowFromPoint failed at (%s, %s)", x, y, exc_info=True)
        return None


def get_window_icon_handle(hwnd: int) -> int | None:
    """Return an HICON for the window (caller must not destroy; lifetime is system-managed)."""
    if not is_windows():
        return None
    try:
        import win32con
        import win32gui

        hwnd = int(hwnd)
        for msg, size in (
            (win32con.WM_GETICON, win32con.ICON_BIG),
            (win32con.WM_GETICON, win32con.ICON_SMALL),
            (win32con.WM_GETICON, 2),
        ):
            icon = win32gui.SendMessage(hwnd, msg, size, 0)
            if icon:
                return int(icon)

        class_name = win32gui.GetClassName(hwnd)
        if class_name:
            import win32api

            icon = win32api.LoadImage(
                0,
                class_name,
                win32con.IMAGE_ICON,
                16,
                16,
                win32con.LR_SHARED,
            )
            if icon:
                return int(icon)

        process_name = _process_name_for_hwnd(hwnd)
        if process_name:
            return _icon_from_exe(process_name)
    except Exception:
        log.debug("get_window_icon_handle failed hwnd=%s", hwnd, exc_info=True)
    return None


def _icon_from_exe(process_name: str) -> int | None:
    try:
        import ctypes
        import win32con
        from ctypes import wintypes

        shfileinfo = wintypes.SHFILEINFO()
        flags = win32con.SHGFI_ICON | win32con.SHGFI_SMALLICON
        shell32 = ctypes.windll.shell32
        # Resolve full path via running process is already done; use generic lookup
        if not shell32.SHGetFileInfoW(
            process_name,
            0,
            ctypes.byref(shfileinfo),
            ctypes.sizeof(shfileinfo),
            flags,
        ):
            return None
        return int(shfileinfo.hIcon) if shfileinfo.hIcon else None
    except Exception:
        return None


class WindowService:
    """Windows API facade for inject target discovery."""

    def __init__(self, *, exclude_hwnds: Iterable[int] | None = None) -> None:
        self._exclude_hwnds = _normalize_exclude_hwnds(exclude_hwnds)

    def set_exclude_hwnds(self, exclude_hwnds: Iterable[int] | None) -> None:
        self._exclude_hwnds = _normalize_exclude_hwnds(exclude_hwnds)

    def enumerate_windows(
        self,
        *,
        progress: Callable[[], None] | None = None,
    ) -> list[WindowInfo]:
        """List injectable taskbar windows, sorted by title."""
        if not is_windows():
            return []

        results: list[WindowInfo] = []
        excluded = self._exclude_hwnds

        def _callback(hwnd: int, _lparam: int) -> bool:
            if progress is not None:
                progress()
            if not is_taskbar_window(hwnd, excluded=excluded):
                return True
            title = ""
            try:
                import win32gui

                title = (win32gui.GetWindowText(int(hwnd)) or "").strip()
            except Exception:
                return True
            process_name = _process_name_for_hwnd(int(hwnd))
            results.append(
                WindowInfo(
                    hwnd=int(hwnd),
                    title=title,
                    process_name=process_name,
                )
            )
            return True

        try:
            import win32gui

            win32gui.EnumWindows(_callback, 0)
        except Exception:
            log.warning("EnumWindows failed", exc_info=True)
            return []

        results.sort(key=lambda w: (w.get("process_name", "").lower(), w.get("title", "").lower()))
        return results

    def window_at_screen_point(self, x: int, y: int) -> WindowInfo | None:
        """Resolve the taskbar window under a screen coordinate (crosshair picker)."""
        excluded = self._exclude_hwnds
        hwnd = _top_level_hwnd_from_point(x, y, excluded=excluded)
        if hwnd is None:
            return None
        try:
            import win32gui

            title = (win32gui.GetWindowText(int(hwnd)) or "").strip()
        except Exception:
            title = "Unknown window"
        return WindowInfo(
            hwnd=int(hwnd),
            title=title or "Unknown window",
            process_name=_process_name_for_hwnd(int(hwnd)),
        )

    @staticmethod
    def to_foreground_target(info: WindowInfo | None) -> ForegroundTarget:
        if not info:
            return {}
        target: ForegroundTarget = {
            "hwnd": int(info["hwnd"]),
            "title": str(info.get("title") or "Unknown window"),
        }
        process_name = info.get("process_name")
        if process_name:
            target["process_name"] = process_name
        return target

    def find_best_for_process(self, process_name: str) -> WindowInfo | None:
        """Pick the best open window for a process executable name."""
        needle = (process_name or "").strip().lower()
        if not needle:
            return None
        windows = self.enumerate_windows()
        exact = [w for w in windows if w.get("process_name", "").lower() == needle]
        if not exact:
            exact = [w for w in windows if needle in w.get("process_name", "").lower()]
        if not exact:
            return None
        try:
            import win32gui

            fg = int(win32gui.GetForegroundWindow())
            for w in exact:
                if int(w["hwnd"]) == fg:
                    return w
        except Exception:
            pass
        return exact[0]

    def resolve_inject_target(
        self,
        preference: InjectTargetPreference,
        *,
        own_hwnd: int | None = None,
        refresh_dynamic: bool = True,
    ) -> ForegroundTarget:
        """
        Resolve the inject target from user preference, project binding, or foreground.

        Priority: project process binding → pinned HWND → dynamic foreground capture.
        """
        if preference.project_process:
            match = self.find_best_for_process(preference.project_process)
            if match:
                target = self.to_foreground_target(match)
                if self._target_usable(target, own_hwnd=own_hwnd):
                    return target

        if preference.mode == INJECT_TARGET_PINNED and preference.pinned_hwnd:
            hwnd = int(preference.pinned_hwnd)
            if is_target_valid(hwnd) and not is_self_target(
                {"hwnd": hwnd, "process_name": _process_name_for_hwnd(hwnd)},
                own_hwnd=own_hwnd,
            ):
                title = ""
                try:
                    import win32gui

                    title = (win32gui.GetWindowText(hwnd) or "").strip()
                except Exception:
                    title = "Unknown window"
                process_name = _process_name_for_hwnd(hwnd)
                if not is_blocked_target(title, process_name):
                    target: ForegroundTarget = {
                        "hwnd": hwnd,
                        "title": title or "Unknown window",
                    }
                    if process_name:
                        target["process_name"] = process_name
                    return target

        if refresh_dynamic:
            captured = record_foreground_target(exclude_hwnds=self._exclude_hwnds)
            if self._target_usable(captured, own_hwnd=own_hwnd):
                return captured
        return {}

    @staticmethod
    def _target_usable(target: ForegroundTarget, *, own_hwnd: int | None) -> bool:
        if not target or not target.get("hwnd"):
            return False
        if not is_target_valid(int(target["hwnd"])):
            return False
        if is_self_target(target, own_hwnd=own_hwnd):
            return False
        return not is_blocked_target(target.get("title"), target.get("process_name"))
