"""
Windows Startup-folder helpers for MetaPrompt auto-launch on login.
"""

from __future__ import annotations

import sys
from pathlib import Path

from config import APP_DIR, load_config, save_config

# Shortcut / launcher name inside the user's Startup folder
STARTUP_NAME = "MetaPrompt.bat"


def _startup_folder() -> Path:
    # %APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup
    appdata = Path.home() / "AppData" / "Roaming"
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def startup_shortcut_path() -> Path:
    return _startup_folder() / STARTUP_NAME


def is_start_with_windows_enabled() -> bool:
    return startup_shortcut_path().exists()


def enable_start_with_windows() -> Path:
    """
    Write a .bat launcher into the Startup folder that runs main.py with pythonw
    (no console window). Returns the path to the created file.
    """
    startup = _startup_folder()
    startup.mkdir(parents=True, exist_ok=True)
    target = startup_shortcut_path()

    main_py = APP_DIR / "main.py"
    # Prefer pythonw.exe so no console flashes on login
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    interpreter = str(pythonw if pythonw.exists() else python)

    # /d sets drive+dir; quote paths for spaces (e.g. "_Coding Projects")
    bat = (
        "@echo off\r\n"
        f'cd /d "{APP_DIR}"\r\n'
        f'start "" "{interpreter}" "{main_py}"\r\n'
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
