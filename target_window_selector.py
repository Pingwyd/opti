"""
PyQt6 inject target selector for the result-panel inject row.

Dropdown refresh runs off the main thread; window pick is a menu action.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PyQt6.QtCore import QPoint, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QKeyEvent, QMouseEvent, QPixmap
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QMenu, QWidget

from ui_theme import settings_font, FONT_CAPTION
from window_service import (
    INJECT_TARGET_DYNAMIC,
    INJECT_TARGET_PINNED,
    WindowInfo,
    WindowService,
)

log = logging.getLogger(__name__)

DYNAMIC_LABEL = "Last active window"


def _icon_from_hwnd(hwnd: int) -> QIcon:
    if not hwnd:
        return QIcon()
    try:
        from window_service import get_window_icon_handle

        hicon = get_window_icon_handle(int(hwnd))
        if hicon:
            pixmap = QPixmap.fromWinHICON(int(hicon))
            if not pixmap.isNull():
                return QIcon(pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio))
    except Exception:
        log.debug("icon conversion failed hwnd=%s", hwnd, exc_info=True)
    return QIcon()


class _EnumerateWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, service: WindowService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service

    def run(self) -> None:
        try:
            windows = self._service.enumerate_windows()
        except Exception:
            log.warning("window enumeration worker failed", exc_info=True)
            windows = []
        self.finished.emit(windows)


class _WindowPickerOverlay(QWidget):
    """Fullscreen overlay — click a visible window to pin it as inject target."""

    windowPicked = pyqtSignal(object)
    cancelled = pyqtSignal()

    def __init__(self, service: WindowService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setObjectName("windowPickerOverlay")

    def show_fullscreen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.geometry())
        self.show()
        self.raise_()
        self.activateWindow()

    def paintEvent(self, event) -> None:  # noqa: ANN001, N802
        from PyQt6.QtGui import QColor, QPainter

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 40))
        painter.end()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        pos = event.globalPosition().toPoint()
        info = self._service.window_at_screen_point(pos.x(), pos.y())
        if info:
            self.windowPicked.emit(info)
        else:
            self.cancelled.emit()
        self.close()
        event.accept()


class InjectTargetSelector(QFrame):
    """Dropdown target picker for the inject row (no crosshair button on the bar)."""

    targetChanged = pyqtSignal(str, object)  # mode, WindowInfo | None

    def __init__(self, service: WindowService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("injectTargetSelector")
        self._service = service
        self._mode = INJECT_TARGET_DYNAMIC
        self._pinned: WindowInfo | None = None
        self._worker: _EnumerateWorker | None = None
        self._picker: _WindowPickerOverlay | None = None
        self._menu: QMenu | None = None
        self._no_target = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._button = QFrame(self)
        self._button.setObjectName("injectTargetSelectorButton")
        self._button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._button.setMinimumWidth(160)
        btn_layout = QHBoxLayout(self._button)
        btn_layout.setContentsMargins(10, 0, 8, 0)
        btn_layout.setSpacing(8)
        self._icon_label = QLabel(self._button)
        self._icon_label.setFixedSize(16, 16)
        self._icon_label.setScaledContents(True)
        self._text_label = QLabel(DYNAMIC_LABEL, self._button)
        self._text_label.setFont(settings_font(FONT_CAPTION))
        self._text_label.setMinimumWidth(120)
        btn_layout.addWidget(self._icon_label, 0)
        btn_layout.addWidget(self._text_label, 1)
        layout.addWidget(self._button, 1)

        self._button.mousePressEvent = self._on_button_clicked  # type: ignore[method-assign]
        self._refresh_display()

    def mode(self) -> str:
        return self._mode

    def pinned_hwnd(self) -> int | None:
        return int(self._pinned["hwnd"]) if self._pinned else None

    def set_no_target_hint(self, missing: bool) -> None:
        """Show a muted hint when no injectable window is resolved yet."""
        self._no_target = missing
        self._refresh_display()

    def set_dynamic(self, *, emit: bool = True) -> None:
        self._mode = INJECT_TARGET_DYNAMIC
        self._pinned = None
        self._no_target = False
        self._refresh_display()
        if emit:
            self.targetChanged.emit(self._mode, None)

    def set_pinned_window(self, info: WindowInfo, *, emit: bool = True) -> None:
        self._mode = INJECT_TARGET_PINNED
        self._pinned = info
        self._no_target = False
        self._refresh_display()
        if emit:
            self.targetChanged.emit(self._mode, info)

    def current_target_dict(self) -> dict[str, int | str] | None:
        """Return the inject target this selector would use right now."""
        if self._mode == INJECT_TARGET_PINNED and self._pinned:
            return {
                "hwnd": int(self._pinned["hwnd"]),
                "title": str(self._pinned.get("title") or "Window"),
                "process_name": str(self._pinned.get("process_name") or ""),
            }
        return None

    def load_preference(self, mode: str, pinned_hwnd: int | None) -> None:
        if mode == INJECT_TARGET_PINNED and pinned_hwnd:
            windows = self._service.enumerate_windows()
            for w in windows:
                if int(w["hwnd"]) == int(pinned_hwnd):
                    self._mode = INJECT_TARGET_PINNED
                    self._pinned = w
                    self._no_target = False
                    self._refresh_display()
                    return
        self._mode = INJECT_TARGET_DYNAMIC
        self._pinned = None
        self._refresh_display()

    def reflect_resolved_target(self, target: dict | None, *, mode: str) -> None:
        """Update the label to show the resolved target (dynamic mode shows actual window title)."""
        if self._mode == INJECT_TARGET_PINNED and self._pinned:
            self._refresh_display()
            return

        if not target or not target.get("hwnd"):
            self._no_target = True
            self._refresh_display()
            return

        self._no_target = False
        if mode == INJECT_TARGET_DYNAMIC:
            title = str(target.get("title") or "Window")
            display = title if len(title) <= 36 else title[:34] + "…"
            self._text_label.setText(display)
            hwnd = int(target["hwnd"])
            icon = _icon_from_hwnd(hwnd)
            pix = icon.pixmap(16, 16)
            self._icon_label.setPixmap(pix if not pix.isNull() else QPixmap())
            process = str(target.get("process_name") or "")
            tip = f"{title} ({process})" if process else title
            tip = f"{tip}\n(Dynamic — last active when opened)"
            self._button.setToolTip(tip)
            return

        self._refresh_display()

    def _refresh_display(self) -> None:
        if self._no_target and self._mode == INJECT_TARGET_DYNAMIC:
            self._text_label.setText("No target — pick a window")
            self._icon_label.clear()
            self._button.setToolTip(
                "No injectable window found. Choose one from the list or pick on screen."
            )
            return

        if self._mode == INJECT_TARGET_PINNED and self._pinned:
            title = str(self._pinned.get("title") or "Window")
            process = str(self._pinned.get("process_name") or "")
            display = title if len(title) <= 36 else title[:34] + "…"
            self._text_label.setText(display)
            icon = _icon_from_hwnd(int(self._pinned["hwnd"]))
            pix = icon.pixmap(16, 16)
            self._icon_label.setPixmap(pix if not pix.isNull() else QPixmap())
            tip = title
            if process:
                tip = f"{title} ({process})"
            self._button.setToolTip(tip)
            return

        self._text_label.setText(DYNAMIC_LABEL)
        self._icon_label.clear()
        self._button.setToolTip(
            "Inject into the window that was active when you opened Opti, "
            "or when you last picked a target."
        )

    def _on_button_clicked(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._open_menu()
            event.accept()

    def _open_menu(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        menu = QMenu(self)
        menu.setObjectName("targetWindowMenu")
        loading = menu.addAction("Loading windows…")
        loading.setEnabled(False)
        menu.popup(self._button.mapToGlobal(QPoint(0, self._button.height())))

        self._menu = menu
        self._worker = _EnumerateWorker(self._service, self)
        self._worker.finished.connect(lambda windows: self._populate_menu(menu, loading, windows))
        self._worker.start()

    def _populate_menu(self, menu: QMenu, loading_action, windows: list) -> None:
        if menu is not self._menu:
            return
        menu.removeAction(loading_action)

        dynamic = menu.addAction(DYNAMIC_LABEL)
        dynamic.setCheckable(True)
        dynamic.setChecked(self._mode == INJECT_TARGET_DYNAMIC and not self._no_target)
        dynamic.triggered.connect(lambda: self.set_dynamic())

        if windows:
            menu.addSeparator()
        for info in windows:
            title = str(info.get("title") or "Unknown")
            process = str(info.get("process_name") or "")
            label = f"{title} ({process})" if process else title
            if len(label) > 72:
                label = label[:70] + "…"
            action = menu.addAction(_icon_from_hwnd(int(info["hwnd"])), label)
            action.setCheckable(True)
            checked = (
                self._mode == INJECT_TARGET_PINNED
                and self._pinned is not None
                and int(self._pinned["hwnd"]) == int(info["hwnd"])
            )
            action.setChecked(checked)

            def _make_handler(window_info: WindowInfo) -> Callable[[], None]:
                return lambda: self.set_pinned_window(window_info)

            action.triggered.connect(_make_handler(info))

        menu.addSeparator()
        pick_action = menu.addAction("Pick window on screen…")
        pick_action.triggered.connect(self._start_picker)

    def _start_picker(self) -> None:
        if self._picker is None:
            self._picker = _WindowPickerOverlay(self._service, None)
            self._picker.windowPicked.connect(self.set_pinned_window)
        self._picker.show_fullscreen()

    def closeEvent(self, event) -> None:  # noqa: ANN001, N802
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(500)
        super().closeEvent(event)


# Backward-compatible alias
TargetWindowChip = InjectTargetSelector
