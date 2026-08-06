"""
Resolve install bundle dir vs user-writable data directory.

Development: data lives next to source.
Installed:   %LOCALAPPDATA%\\Opti\\
Portable:    folder containing Opti.exe when portable.txt is present
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from brand import APP_NAME

# Source / bundle root (read-only when frozen)
if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    INSTALL_DIR = Path(sys.executable).resolve().parent
else:
    BUNDLE_DIR = Path(__file__).resolve().parent
    INSTALL_DIR = BUNDLE_DIR


def is_portable_install() -> bool:
    if not getattr(sys, "frozen", False):
        return False
    return (INSTALL_DIR / "portable.txt").is_file()


def get_data_dir() -> Path:
    """Directory for config.json, history, drafts, logs."""
    if getattr(sys, "frozen", False):
        if is_portable_install():
            return INSTALL_DIR
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return base / APP_NAME
    return Path(__file__).resolve().parent


def ensure_data_dir() -> Path:
    data = get_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    return data
