"""
Opti — Windows tray app entry point.

Starts:
  - QApplication (PyQt6) on the main thread
  - system tray icon (pystray) in a daemon thread
  - global hotkey listener (pynput) in a daemon thread
  - frameless PyQt6 popup (shown on hotkey)

Run from this directory:
  python main.py

Prefer pythonw.exe for a console-less background process.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

# Ensure the package directory is on sys.path when launched as a script
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from brand import APP_NAME, APP_VERSION, TRAY_TOOLTIP  # noqa: E402
from config import (  # noqa: E402
    get_check_updates_on_launch,
    get_hotkey,
    get_hotkey_collapse,
    get_start_minimized_to_tray,
    has_api_key,
)
from hotkey_service import GlobalHotkeyService  # noqa: E402
from log_config import setup_logging  # noqa: E402
from popup import controller  # noqa: E402
from settings_ui import SettingsDialog  # noqa: E402
from startup import (  # noqa: E402
    apply_start_with_windows_from_config,
    disable_start_with_windows,
    enable_start_with_windows,
    is_start_with_windows_enabled,
)

log = logging.getLogger(__name__)

# Shared refs for clean shutdown (set during startup)
_tray_icon: dict[str, Any] = {"icon": None}
_hotkey_service: GlobalHotkeyService | None = None


def make_tray_icon_image():
    """Create a simple tray icon with Pillow (no external asset required)."""
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Dark rounded square with coral spark accent
    draw.rounded_rectangle((4, 4, size - 4, size - 4), radius=14, fill=(20, 20, 22, 255))
    draw.ellipse((22, 20, 42, 40), fill=(240, 128, 96, 230))
    draw.ellipse((30, 34, 44, 48), fill=(240, 128, 96, 140))
    return img


def start_tray(on_quit, icon_holder: dict[str, Any]) -> None:
    """Run pystray icon in a daemon thread."""
    import pystray
    from pystray import MenuItem as Item

    def show_popup(icon=None, item=None):  # noqa: ARG001
        controller.show_expanded()

    def open_history(icon=None, item=None):  # noqa: ARG001
        controller.show_history()

    def open_settings(icon=None, item=None):  # noqa: ARG001
        controller.show_settings()

    def reset_window_position(icon=None, item=None):  # noqa: ARG001
        controller.reset_window_position()

    def toggle_startup(icon=None, item=None):  # noqa: ARG001
        if is_start_with_windows_enabled():
            disable_start_with_windows()
        else:
            enable_start_with_windows()

    def quit_app(icon=None, item=None):  # noqa: ARG001
        log.info("Tray menu: Quit selected")
        on_quit()

    menu = pystray.Menu(
        Item(f"Open {APP_NAME}", show_popup, default=True),
        Item("Reset window position", reset_window_position),
        Item("Open history", open_history),
        Item("Settings", open_settings),
        pystray.Menu.SEPARATOR,
        Item(
            "Start with Windows",
            toggle_startup,
            checked=lambda item: is_start_with_windows_enabled(),  # noqa: ARG005
        ),
        Item("Quit", quit_app),
    )

    icon = pystray.Icon(
        APP_NAME,
        make_tray_icon_image(),
        TRAY_TOOLTIP,
        menu,
    )
    icon_holder["icon"] = icon
    log.info("Tray icon starting")
    # blocking; run in thread
    icon.run()
    log.info("Tray icon run loop exited")


def _global_hotkey_bindings() -> dict[str, Any]:
    return {
        get_hotkey(): controller.toggle_from_hotkey,
        get_hotkey_collapse(): controller.toggle_collapse_global_from_hotkey,
    }


def reload_global_hotkey() -> None:
    """Re-read config and restart the pynput listener (no app restart)."""
    global _hotkey_service
    if _hotkey_service is None:
        return
    _hotkey_service.restart(_global_hotkey_bindings())


def stop_hotkey_listener() -> None:
    global _hotkey_service
    if _hotkey_service is None:
        return
    _hotkey_service.stop()
    _hotkey_service = None


def stop_tray_icon() -> None:
    icon = _tray_icon.get("icon")
    if icon is None:
        return
    try:
        icon.stop()
        log.info("Tray icon stop requested")
    except Exception:
        log.warning("Tray icon stop failed", exc_info=True)
    finally:
        _tray_icon["icon"] = None


def main() -> None:
    setup_logging()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    apply_start_with_windows_from_config()

    # First-run API key prompt (PyQt6 dialog)
    if not has_api_key():
        SettingsDialog.run_if_needed()

    global _hotkey_service
    quit_flag = {"done": False}
    force_exit_timer: QTimer | None = None

    def force_exit() -> None:
        log.warning("Force exit fallback (os._exit)")
        os._exit(0)

    def schedule_force_exit() -> None:
        nonlocal force_exit_timer
        if force_exit_timer is not None:
            return
        force_exit_timer = QTimer()
        force_exit_timer.setSingleShot(True)
        force_exit_timer.timeout.connect(force_exit)
        force_exit_timer.start(1500)
        log.info("Scheduled force-exit fallback in 1.5s")

    def shutdown_main_thread() -> None:
        if quit_flag["done"]:
            log.debug("Shutdown already in progress; ignoring duplicate quit")
            return
        quit_flag["done"] = True
        log.info("Shutdown: begin")

        try:
            if controller.window is not None:
                controller.window._position_save_timer.stop()
                controller.window._persist_window_position(force=True)
                if controller.window.isVisible():
                    controller.window.flush_draft()
        except Exception:
            log.warning("Draft save failed during quit", exc_info=True)

        try:
            controller.destroy()
        except Exception:
            log.warning("Popup destroy failed during quit", exc_info=True)

        stop_hotkey_listener()
        stop_tray_icon()

        try:
            app.quit()
            log.info("Shutdown: QApplication.quit() called")
        except Exception:
            log.warning("QApplication.quit failed", exc_info=True)

        schedule_force_exit()
        log.info("Shutdown: complete (waiting for event loop exit)")

    def request_quit() -> None:
        controller.request_quit()

    controller.set_quit_callback(shutdown_main_thread)
    controller.set_settings_saved_callback(reload_global_hotkey)

    app.screenAdded.connect(lambda _screen: controller.validate_window_position())
    app.screenRemoved.connect(lambda _screen: controller.validate_window_position())

    # Tray (daemon thread)
    tray_thread = threading.Thread(
        target=start_tray,
        args=(request_quit, _tray_icon),
        name="OptiTray",
        daemon=True,
    )
    tray_thread.start()

    # Global hotkeys (toggle show/hide + collapse/expand chip)
    _hotkey_service = GlobalHotkeyService()
    _hotkey_service.start(_global_hotkey_bindings())

    # Create popup and run Qt event loop on the main thread (required on Windows)
    controller.create_window()

    if get_check_updates_on_launch():
        log.debug("Update check on launch is enabled (stub — not implemented)")

    if not get_start_minimized_to_tray():
        controller.show_expanded()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
