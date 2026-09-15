"""PyInstaller runtime hook: locate bundled Qt platform plugins when frozen."""

from __future__ import annotations

import os
import sys


def _configure_qt_plugins() -> None:
    if not getattr(sys, "frozen", False):
        return
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return
    for sub in (
        os.path.join("PyQt6", "Qt6", "plugins"),
        os.path.join("PyQt6", "Qt", "plugins"),
    ):
        plugin_path = os.path.join(base, sub)
        if os.path.isdir(plugin_path):
            os.environ.setdefault("QT_PLUGIN_PATH", plugin_path)
            break


_configure_qt_plugins()
