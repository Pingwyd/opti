"""
Windows Startup-folder helpers for Opti auto-launch on login.
"""

from __future__ import annotations

import sys
from pathlib import Path

from brand import APP_NAME
from config import load_config, save_config
from paths import BUNDLE_DIR, INSTALL_DIR

# Shortcut / launcher name inside the user's Startup folder
STARTUP_NAME = f"{APP_NAME}.bat"


def _startup_folder() -> Path:
    # %APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup
    appdata = Path.home() / "AppData" / "Roaming"
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def startup_shortcut_path() -> Path:
    return _startup_folder() / STARTUP_NAME


def is_start_with_windows_enabled() -> bool:
    return startup_shortcut_path().exists()


def _launch_command() -> tuple[str, str]:
    """Return (working_directory, command_line) for the startup .bat."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        return str(exe.parent), f'start "" "{exe}"'
    main_py = BUNDLE_DIR / "main.py"
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    interpreter = str(pythonw if pythonw.exists() else python)
    return str(BUNDLE_DIR), f'start "" "{interpreter}" "{main_py}"'


def enable_start_with_windows() -> Path:
    """
    Write a .bat launcher into the Startup folder.
    Returns the path to the created file.
    """
    startup = _startup_folder()
    startup.mkdir(parents=True, exist_ok=True)
    target = startup_shortcut_path()

    work_dir, launch = _launch_command()
    bat = (
        "@echo off\r\n"
        f'cd /d "{work_dir}"\r\n'
        f"{launch}\r\n"
    )
    target.write_text(bat, encoding="utf-8")

    cfg = load_config()
    cfg["start_with_windows"] = True
    save_config(cfg)
    return target


def disable_start_with_windows() -> None:
    path = startup_shortcut_path()
    if path.exists():
        path.unlink()
    cfg = load_config()
    cfg["start_with_windows"] = False
    save_config(cfg)


def apply_start_with_windows_from_config() -> None:
    """On startup, align the Startup-folder shortcut with config.json."""
    cfg = load_config()
    want = bool(cfg.get("start_with_windows"))
    have = is_start_with_windows_enabled()
    if want and not have:
        enable_start_with_windows()
    elif not want and have:
        path = startup_shortcut_path()
        if path.exists():
            path.unlink()
