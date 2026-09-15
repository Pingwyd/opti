"""
PyQt6 history browser: searchable list with detail pane and row hover actions.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from PyQt6.QtCore import (
    QAbstractListModel,
    QEasingCurve,
    QModelIndex,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QThread,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFontMetrics,
    QGuiApplication,
    QKeyEvent,
    QPainter,
    QPen,
    QTextBlockFormat,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScroller,
    QSplitter,
    QStackedWidget,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QListView,
    QStyle,
)

from config import (
    get_history_window_geometry,
    load_config,
    save_config,
    set_history_window_geometry,
    validate_window_position,
)
from history import delete_entry, get_entries, history_file_path
from projects import list_projects
from widgets import ToggleSwitch
from ui_theme import (
    BORDER,
    BORDER_STRONG,
    BORDER_SUBTLE,
    CORAL,
    CORAL_TINT,
    FONT_CAPTION,
    FONT_MICRO,
    FONT_SMALL,
    FONT_TITLE,
    HOVER_TINT,
    SUCCESS,
    TEXT_BODY,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WEIGHT_MEDIUM,
    WEIGHT_REGULAR,
    history_stylesheet,
    project_color,
    settings_font,
    settings_mono_font,
)

SEARCH_DEBOUNCE_MS = 200
COPY_CONFIRM_MS = 1200
DELETE_FADE_MS = 180
ROW_MARGIN_H = 12
ROW_MARGIN_V = 11
ROW_SPACING = 5
ACTION_ICON = 13
ACTION_HIT = 22
ACTION_GAP = 6

_DATE_RANGE_OPTIONS: tuple[tuple[str, int | None], ...] = (
    ("All time", None),
    ("Last 7 days", 7),
    ("Last 30 days", 30),
    ("Last 90 days", 90),
)

EntryRole = Qt.ItemDataRole.UserRole
PreviewRole = Qt.ItemDataRole.UserRole + 1
OpacityRole = Qt.ItemDataRole.UserRole + 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\n", " ").replace("\r", " ")).strip()


def _format_relative_time(ts: str) -> str:
    parsed = None
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return ts
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone()
    now = datetime.now().astimezone()
    diff = now - local
    if diff < timedelta(minutes=1):
        return "Just now"
    if diff < timedelta(hours=1):
        mins = int(diff.total_seconds() / 60)
        return f"{mins} min{'s' if mins != 1 else ''} ago"
    if diff < timedelta(days=1):
        hours = int(diff.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    if diff < timedelta(days=7):
        days = diff.days
        return f"{days} day{'s' if days != 1 else ''} ago"
    return local.strftime("%Y-%m-%d %H:%M")


def _absolute_timestamp(ts: str) -> str:
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ts


def _entry_is_private(entry: dict[str, Any]) -> bool:
    if entry.get("private"):
        return True
    tags = [str(t).lower() for t in entry.get("tags") or []]
    return "private" in tags


def _screens_for_validation() -> list[tuple[int, int, int, int]]:
    screens: list[tuple[int, int, int, int]] = []
    for screen in QGuiApplication.screens():
        geo = screen.geometry()
        screens.append((geo.x(), geo.y(), geo.width(), geo.height()))
    return screens


# ---------------------------------------------------------------------------
# QPainter-drawn icons (no icon fonts)
# ---------------------------------------------------------------------------


def _paint_magnifier(painter: QPainter, rect: QRectF, color: str) -> None:
    pen = QPen(QColor(color))
    pen.setWidthF(1.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    cx, cy = rect.center().x(), rect.center().y()
    r = min(rect.width(), rect.height()) * 0.28
    painter.drawEllipse(QPointF(cx - 1.5, cy - 1.5), r, r)
    painter.drawLine(QPointF(cx + r * 0.65, cy + r * 0.65), QPointF(rect.right() - 2, rect.bottom() - 2))


def _paint_chevron(painter: QPainter, rect: QRectF, color: str, *, down: bool = True) -> None:
    pen = QPen(QColor(color))
    pen.setWidthF(1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    cx, cy = rect.center().x(), rect.center().y()
    half = min(rect.width(), rect.height()) * 0.22
    if down:
        painter.drawLine(QPointF(cx - half, cy - half * 0.4), QPointF(cx, cy + half * 0.5))
        painter.drawLine(QPointF(cx, cy + half * 0.5), QPointF(cx + half, cy - half * 0.4))
    else:
        painter.drawLine(QPointF(cx - half, cy + half * 0.4), QPointF(cx, cy - half * 0.5))
        painter.drawLine(QPointF(cx, cy - half * 0.5), QPointF(cx + half, cy + half * 0.4))


def _paint_combo_chevron(painter: QPainter, rect: QRectF, color: str) -> None:
    _paint_chevron(painter, rect, color, down=True)


def _paint_copy_icon(painter: QPainter, rect: QRectF, color: str) -> None:
    pen = QPen(QColor(color))
    pen.setWidthF(1.3)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    inset = rect.width() * 0.18
    back = QRectF(rect.left() + inset + 3, rect.top() + inset, rect.width() - inset * 2 - 3, rect.height() - inset * 2)
    front = QRectF(rect.left() + inset, rect.top() + inset + 3, rect.width() - inset * 2 - 3, rect.height() - inset * 2)
    painter.drawRoundedRect(back, 2, 2)
    painter.drawRoundedRect(front, 2, 2)


def _paint_check_icon(painter: QPainter, rect: QRectF, color: str) -> None:
    pen = QPen(QColor(color))
    pen.setWidthF(1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    cx, cy = rect.center().x(), rect.center().y()
    painter.drawLine(QPointF(cx - 4, cy), QPointF(cx - 1, cy + 3))
    painter.drawLine(QPointF(cx - 1, cy + 3), QPointF(cx + 5, cy - 3))


def _paint_restore_icon(painter: QPainter, rect: QRectF, color: str) -> None:
    pen = QPen(QColor(color))
    pen.setWidthF(1.3)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    cx, cy = rect.center().x(), rect.center().y()
    painter.drawArc(QRectF(cx - 5, cy - 5, 10, 10), 45 * 16, 270 * 16)
    painter.drawLine(QPointF(cx + 3, cy - 5), QPointF(cx + 6, cy - 5))
    painter.drawLine(QPointF(cx + 6, cy - 5), QPointF(cx + 6, cy - 2))


def _paint_delete_icon(painter: QPainter, rect: QRectF, color: str) -> None:
    pen = QPen(QColor(color))
    pen.setWidthF(1.3)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    cx, cy = rect.center().x(), rect.center().y()
    painter.drawLine(QPointF(cx - 4, cy - 3), QPointF(cx + 4, cy + 3))
    painter.drawLine(QPointF(cx + 4, cy - 3), QPointF(cx - 4, cy + 3))


def _paint_empty_history_icon(painter: QPainter, rect: QRectF, color: str) -> None:
    pen = QPen(QColor(color))
    pen.setWidthF(1.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    body = QRectF(rect.left() + rect.width() * 0.22, rect.top() + rect.height() * 0.18, rect.width() * 0.56, rect.height() * 0.62)
    painter.drawRoundedRect(body, 4, 4)
    painter.drawLine(
        QPointF(body.left() + 8, body.top() + 10),
        QPointF(body.right() - 8, body.top() + 10),
    )
    painter.drawLine(
        QPointF(body.left() + 8, body.top() + 18),
        QPointF(body.right() - 14, body.top() + 18),
    )


# ---------------------------------------------------------------------------
# Background loader
# ---------------------------------------------------------------------------


class _HistoryLoadWorker(QThread):
    loaded = pyqtSignal(list)

    def run(self) -> None:
        entries = get_entries()
        self.loaded.emit(entries)


# ---------------------------------------------------------------------------
# List model
# ---------------------------------------------------------------------------


class HistoryListModel(QAbstractListModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[dict[str, Any]] = []

    def set_entries(self, entries: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self.endResetModel()

    def entries(self) -> list[dict[str, Any]]:
        return self._entries

    def entry_at(self, row: int) -> dict[str, Any] | None:
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None

    def row_for_id(self, entry_id: str) -> int:
        for i, entry in enumerate(self._entries):
            if str(entry.get("id") or "") == entry_id:
                return i
        return -1

    def remove_entry_id(self, entry_id: str) -> None:
        row = self.row_for_id(entry_id)
        if row < 0:
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._entries[row]
        self.endRemoveRows()

    def set_opacity(self, row: int, opacity: float) -> None:
        if 0 <= row < len(self._entries):
            idx = self.index(row, 0)
            self.setData(idx, float(opacity), OpacityRole)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._entries)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if not index.isValid() or index.row() >= len(self._entries):
            return None
        entry = self._entries[index.row()]
        if role == EntryRole:
            return entry
        if role == PreviewRole:
            return _collapse_whitespace(str(entry.get("input") or entry.get("output") or ""))
        if role == OpacityRole:
            return entry.get("_opacity", 1.0)
        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:  # noqa: N802
        if not index.isValid() or index.row() >= len(self._entries):
            return False
        if role == OpacityRole:
            self._entries[index.row()]["_opacity"] = float(value)
            self.dataChanged.emit(index, index, [OpacityRole])
            return True
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:  # noqa: N802
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


# ---------------------------------------------------------------------------
# Row delegate
# ---------------------------------------------------------------------------


class HistoryRowDelegate(QStyledItemDelegate):
    copy_clicked = pyqtSignal(dict)
    restore_clicked = pyqtSignal(dict)
    delete_clicked = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hover_row = -1
        self._hover_action: str | None = None
        self._copy_confirm_row = -1
        self._copy_timer = QTimer(self)
        self._copy_timer.setSingleShot(True)
        self._copy_timer.timeout.connect(self._clear_copy_confirm)
        self._action_rects: dict[int, dict[str, QRect]] = {}

        self._time_font = settings_font(FONT_CAPTION)
        self._preview_font = settings_font(FONT_SMALL)
        self._model_font = settings_mono_font(FONT_MICRO)
        self._badge_font = settings_font(FONT_CAPTION, WEIGHT_MEDIUM)

        self._row_height = self._compute_row_height()

    def _compute_row_height(self) -> int:
        fm_time = QFontMetrics(self._time_font)
        fm_preview = QFontMetrics(self._preview_font)
        fm_model = QFontMetrics(self._model_font)
        fm_badge = QFontMetrics(self._badge_font)
        line1 = max(fm_badge.height(), fm_time.height())
        line2 = fm_preview.height()
        line3 = fm_model.height()
        content = line1 + ROW_SPACING + line2 + ROW_SPACING + line3
        return content + ROW_MARGIN_V * 2

    def row_height(self) -> int:
        return self._row_height

    def set_hover(self, row: int, action: str | None = None) -> None:
        """Track row- and action-level hover for painting and hit-testing."""
        if row != self._hover_row or action != self._hover_action:
            self._hover_row = row
            self._hover_action = action if row >= 0 else None

    def set_hover_row(self, row: int) -> None:
        self.set_hover(row, None)

    def hit_action(self, row: int, local_pos: QPoint) -> str | None:
        """Return the action id under ``local_pos`` (item-local coordinates)."""
        rects = self._action_rects.get(row)
        if not rects:
            return None
        for action, rect in rects.items():
            if rect.contains(local_pos):
                return action
        return None

    def _request_repaint(self) -> None:
        parent = self.parent()
        if parent is not None:
            viewport = parent.viewport() if hasattr(parent, "viewport") else parent
            viewport.update()

    def show_copy_confirm(self, row: int) -> None:
        self._copy_confirm_row = row
        self._copy_timer.start(COPY_CONFIRM_MS)
        self._request_repaint()

    def _clear_copy_confirm(self) -> None:
        self._copy_confirm_row = -1
        self._request_repaint()

    def sizeHint(self, option, index) -> QSize:  # noqa: ARG002
        return QSize(option.rect.width(), self._row_height)

    def _badge_rect(
        self, painter: QPainter, text: str, x: int, y: int
    ) -> tuple[QRect, int]:
        fm = QFontMetrics(self._badge_font)
        pad_x, pad_y = 9, 3
        w = fm.horizontalAdvance(text) + pad_x * 2
        h = fm.height() + pad_y * 2
        rect = QRect(x, y, w, h)
        fg, bg = project_color(text if text != "No project" else "")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(QRectF(rect), 4, 4)
        painter.setPen(QColor(fg))
        painter.setFont(self._badge_font)
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)
        return rect, w

    def _paint_action_icon(
        self,
        painter: QPainter,
        action: str,
        icon_rect: QRectF,
        *,
        row: int,
        row_opacity: float,
        actions_visible: bool,
    ) -> None:
        if action == "copy" and row == self._copy_confirm_row:
            _paint_check_icon(painter, icon_rect, SUCCESS)
            return
        if not actions_visible:
            return
        hovered = row == self._hover_row and action == self._hover_action
        color = TEXT_PRIMARY if hovered else TEXT_SECONDARY
        painter.setOpacity(row_opacity)
        if action == "copy":
            _paint_copy_icon(painter, icon_rect, color)
        elif action == "restore":
            _paint_restore_icon(painter, icon_rect, color)
        else:
            _paint_delete_icon(painter, icon_rect, color)

    def paint(self, painter, option, index) -> None:
        entry = index.data(EntryRole)
        if not isinstance(entry, dict):
            return

        painter.save()
        row = index.row()
        row_opacity = float(index.data(OpacityRole) or 1.0)
        painter.setOpacity(row_opacity)

        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = row == self._hover_row
        actions_visible = hovered

        if selected:
            painter.fillRect(rect, QColor(CORAL_TINT))
            painter.fillRect(QRect(rect.left(), rect.top(), 2, rect.height()), QColor(CORAL))
        elif hovered:
            painter.fillRect(rect, QColor(HOVER_TINT))

        painter.setPen(QPen(QColor(BORDER_SUBTLE), 0.5))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        # Item-local coordinates simplify hit-testing in editorEvent.
        painter.translate(rect.topLeft())
        local = QRect(0, 0, rect.width(), rect.height())
        inner = local.adjusted(ROW_MARGIN_H, ROW_MARGIN_V, -ROW_MARGIN_H, -ROW_MARGIN_V)
        fm_time = QFontMetrics(self._time_font)
        fm_preview = QFontMetrics(self._preview_font)
        fm_model = QFontMetrics(self._model_font)

        y = inner.top()
        project_name = str(entry.get("project_name") or "").strip() or "No project"
        badge_rect, _badge_w = self._badge_rect(painter, project_name, inner.left(), y)

        ts = _format_relative_time(str(entry.get("timestamp") or ""))
        painter.setFont(self._time_font)
        painter.setPen(QColor(TEXT_MUTED))
        time_w = fm_time.horizontalAdvance(ts)
        time_rect = QRect(inner.right() - time_w, y, time_w, fm_time.height())
        painter.drawText(
            time_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
            ts,
        )

        y = badge_rect.bottom() + ROW_SPACING
        preview = str(index.data(PreviewRole) or "")
        preview_color = TEXT_PRIMARY if selected else TEXT_BODY
        painter.setFont(self._preview_font)
        painter.setPen(QColor(preview_color))
        preview_rect = QRect(inner.left(), y, inner.width(), fm_preview.height())
        elided = fm_preview.elidedText(
            preview, Qt.TextElideMode.ElideRight, preview_rect.width()
        )
        painter.drawText(
            preview_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            elided,
        )

        y = preview_rect.bottom() + ROW_SPACING
        model_id = str(entry.get("model") or "—")
        painter.setFont(self._model_font)
        painter.setPen(QColor(TEXT_MUTED))
        model_rect = QRect(inner.left(), y, inner.width() // 2, fm_model.height())
        painter.drawText(
            model_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            model_id,
        )

        actions = ("copy", "restore", "delete")
        total_w = len(actions) * ACTION_HIT + (len(actions) - 1) * ACTION_GAP
        ax = inner.right() - total_w
        ay = y + (fm_model.height() - ACTION_HIT) // 2
        self._action_rects[row] = {}

        for i, action in enumerate(actions):
            hit = QRect(ax + i * (ACTION_HIT + ACTION_GAP), ay, ACTION_HIT, ACTION_HIT)
            self._action_rects[row][action] = hit
            icon_rect = QRectF(
                hit.x() + (ACTION_HIT - ACTION_ICON) / 2,
                hit.y() + (ACTION_HIT - ACTION_ICON) / 2,
                ACTION_ICON,
                ACTION_ICON,
            )
            self._paint_action_icon(
                painter,
                action,
                icon_rect,
                row=row,
                row_opacity=row_opacity,
                actions_visible=actions_visible,
            )

        painter.restore()

    @staticmethod
    def _local_pos(event, option) -> QPoint:
        return event.position().toPoint() - option.rect.topLeft()

    def _dispatch_action(self, entry: dict[str, Any], action: str, row: int) -> bool:
        if action == "copy":
            self.copy_clicked.emit(entry)
            self.show_copy_confirm(row)
            return True
        if action == "restore":
            self.restore_clicked.emit(entry)
            return True
        if action == "delete":
            self.delete_clicked.emit(entry)
            return True
        return False

    def editorEvent(self, event, model, option, index):  # noqa: ARG002
        if not index.isValid():
            return False
        entry = index.data(EntryRole)
        if not isinstance(entry, dict):
            return False

        row = index.row()
        local_pos = self._local_pos(event, option)
        et = event.type()

        if et == event.Type.MouseMove:
            action = self.hit_action(row, local_pos)
            self.set_hover(row, action)
            self._request_repaint()
            return False

        if event.type() == event.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            action = self.hit_action(row, local_pos)
            if action and row == self._hover_row:
                return self._dispatch_action(entry, action, row)

        return False

    def helpEvent(self, event, view, option, index):  # noqa: ARG002
        entry = index.data(EntryRole)
        if isinstance(entry, dict):
            ts = str(entry.get("timestamp") or "")
            if ts:
                from PyQt6.QtWidgets import QToolTip

                QToolTip.showText(event.globalPos(), _absolute_timestamp(ts), view)
                return True
        return super().helpEvent(event, view, option, index)


# ---------------------------------------------------------------------------
# Custom widgets
# ---------------------------------------------------------------------------


class _SearchField(QWidget):
    textChanged = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._input = QLineEdit(self)
        self._input.setObjectName("historySearch")
        self._input.setPlaceholderText("Search prompts and results")
        self._input.setFont(settings_font(FONT_SMALL))
        self._input.textChanged.connect(self.textChanged.emit)
        layout.addWidget(self._input)

    def text(self) -> str:
        return self._input.text()

    def clear(self) -> None:
        self._input.clear()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        icon_rect = QRectF(12, (self.height() - 16) / 2, 16, 16)
        _paint_magnifier(painter, icon_rect, TEXT_MUTED)
        painter.end()


class _ComboChevronMixin:
    """Paint a dropdown chevron on QComboBox drop-down area."""

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        drop_rect = QRectF(self.width() - 22, 0, 22, self.height())
        _paint_combo_chevron(painter, drop_rect, TEXT_SECONDARY)
        painter.end()


class _DateCombo(_ComboChevronMixin, QComboBox):
    pass


class _ProjectCombo(_ComboChevronMixin, QComboBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("historyProjectFilter")

    def paintEvent(self, event) -> None:  # noqa: ARG002
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        idx = self.currentIndex()
        if idx > 0:
            name = str(self.currentData() or self.currentText())
            fg, _bg = project_color(name)
            swatch = QRectF(10, (self.height() - 10) / 2, 10, 10)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(fg))
            painter.drawRoundedRect(swatch, 2, 2)
        drop_rect = QRectF(self.width() - 22, 0, 22, self.height())
        _paint_combo_chevron(painter, drop_rect, TEXT_SECONDARY)
        painter.end()


class _ChevronButton(QPushButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("detailChevronBtn")
        self.setFixedSize(24, 24)
        self.setToolTip("Collapse")
        self._rotation = 0.0
        self._anim = QPropertyAnimation(self, b"rotation", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._expanded = True

    def _get_rotation(self) -> float:
        return self._rotation

    def _set_rotation(self, value: float) -> None:
        self._rotation = value
        self.update()

    rotation = pyqtProperty(float, fget=_get_rotation, fset=_set_rotation)

    def set_expanded(self, expanded: bool, *, animate: bool = True) -> None:
        self._expanded = expanded
        target = 0.0 if expanded else -90.0
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._rotation)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._rotation = target
            self.update()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._rotation)
        painter.translate(-self.width() / 2, -self.height() / 2)
        _paint_chevron(painter, QRectF(4, 4, 16, 16), TEXT_SECONDARY, down=True)
        painter.end()


class _ContentSizedPromptEdit(QTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("detailInput")
        self.setReadOnly(True)
        self.setFont(settings_font(FONT_SMALL))
        self.document().documentLayout().documentSizeChanged.connect(self._reflow)
        self._max_height = 200

    def set_max_height(self, height: int) -> None:
        self._max_height = max(60, height)
        self._reflow()

    def _reflow(self) -> None:
        doc_h = int(self.document().size().height())
        margins = self.contentsMargins()
        frame = self.frameWidth() * 2
        desired = doc_h + margins.top() + margins.bottom() + frame + 8
        height = min(self._max_height, max(48, desired))
        self.setFixedHeight(height)
        if desired > self._max_height:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        else:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


class _EmptyStateWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)
        self._icon = _EmptyIcon(self)
        self._headline = QLabel("", self)
        self._headline.setObjectName("emptyHeadline")
        self._headline.setFont(settings_font(FONT_SMALL, WEIGHT_MEDIUM))
        self._headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body = QLabel("", self)
        self._body.setObjectName("emptyBody")
        self._body.setFont(settings_font(FONT_CAPTION))
        self._body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body.setWordWrap(True)
        self._clear_btn = QPushButton("Clear filters", self)
        self._clear_btn.setObjectName("emptyClearBtn")
        self._clear_btn.setFont(settings_font(FONT_CAPTION))
        self._clear_btn.hide()
        layout.addWidget(self._icon, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._headline)
        layout.addWidget(self._body)
        layout.addWidget(self._clear_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_state(
        self,
        *,
        headline: str,
        body: str,
        show_clear: bool = False,
        on_clear: Callable[[], None] | None = None,
    ) -> None:
        self._headline.setText(headline)
        self._body.setText(body)
        self._clear_btn.setVisible(show_clear)
        try:
            self._clear_btn.clicked.disconnect()
        except TypeError:
            pass
        if show_clear and on_clear is not None:
            self._clear_btn.clicked.connect(on_clear)


class _EmptyIcon(QWidget):
    def sizeHint(self) -> QSize:
        return QSize(48, 48)

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        _paint_empty_history_icon(painter, QRectF(0, 0, 48, 48), BORDER_STRONG)
        painter.end()


class _CloseButton(QPushButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("historyCloseBtn")
        self.setFixedSize(32, 32)
        self.setToolTip("Close")

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(TEXT_SECONDARY))
        pen.setWidthF(1.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        m = 10
        painter.drawLine(QPointF(m, m), QPointF(self.width() - m, self.height() - m))
        painter.drawLine(QPointF(self.width() - m, m), QPointF(m, self.height() - m))
        painter.end()


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------


class HistoryDialog(QDialog):
    """Searchable history browser with master-detail layout."""

    promptRestored = pyqtSignal(str)
    use_both_requested = pyqtSignal(str, str)
    rerun_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("historyDialog")
        self.setWindowTitle("History")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumSize(900, 600)

        self._drag_pos: QPoint | None = None
        self._all_entries: list[dict[str, Any]] = []
        self._search_index: list[tuple[dict[str, Any], str]] = []
        self._filtered_entries: list[dict[str, Any]] = []
        self._selected_entry: dict[str, Any] | None = None
        self._project_filter: str | None = None
        self._loading = False

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_filters)

        self._load_worker: _HistoryLoadWorker | None = None
        self._geometry_timer = QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.timeout.connect(self._persist_geometry)

        self._build_ui()
        self.setStyleSheet(history_stylesheet())
        self._restore_geometry()
        self._start_load()
        self._apply_split_ratio()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_split_ratio()

    def _apply_split_ratio(self) -> None:
        ratio = getattr(self, "_split_ratio", 0.55)
        total = max(1, self._splitter.width())
        list_w = int(total * ratio)
        self._splitter.setSizes([list_w, max(1, total - list_w)])

    def _restore_geometry(self) -> None:
        x, y, width, height, ratio = get_history_window_geometry()
        self._split_ratio = ratio
        self.resize(width, height)
        if x is not None and y is not None:
            screens = _screens_for_validation()
            nx, ny, _ = validate_window_position(x, y, width, height, screens)
            self.move(nx, ny)
        else:
            self._center_on_screen()

    # --- Geometry persistence ---

    def _center_on_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.x() + (geo.width() - self.width()) // 2,
            geo.y() + (geo.height() - self.height()) // 2,
        )

    def _persist_geometry(self) -> None:
        ratio = 0.55
        if self._splitter.width() > 0:
            ratio = self._splitter.sizes()[0] / max(1, sum(self._splitter.sizes()))
        set_history_window_geometry(self.x(), self.y(), self.width(), self.height(), split_ratio=ratio)

    def _schedule_persist_geometry(self) -> None:
        self._geometry_timer.start(400)

    def closeEvent(self, event) -> None:
        self._persist_geometry()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_prompt_max_height()
        self._schedule_persist_geometry()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._schedule_persist_geometry()

    # --- Drag chrome ---

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    # --- UI construction ---

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        shell = QFrame(self)
        shell.setObjectName("historyShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(20, 16, 20, 16)
        shell_layout.setSpacing(12)
        outer.addWidget(shell)

        title_bar = QWidget(shell)
        title_bar.setObjectName("historyTitleBar")
        header = QHBoxLayout(title_bar)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)

        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel("History", shell)
        title.setObjectName("historyTitle")
        title.setFont(settings_font(FONT_TITLE, WEIGHT_MEDIUM))
        self._count_label = QLabel("", shell)
        self._count_label.setObjectName("historySubtitle")
        self._count_label.setFont(settings_font(FONT_SMALL))
        title_block.addWidget(title)
        title_block.addWidget(self._count_label)
        header.addLayout(title_block)
        header.addStretch()

        private_row = QHBoxLayout()
        private_row.setSpacing(8)
        private_label = QLabel("Private mode", shell)
        private_label.setObjectName("privateModeLabel")
        private_label.setFont(settings_font(FONT_SMALL))
        self._private_toggle = ToggleSwitch(shell)
        self._private_toggle.setToolTip("Disable saving new history entries")
        cfg = load_config()
        self._private_toggle.set_checked_silent(not cfg.get("save_history", True))
        self._private_toggle.toggled.connect(self._on_private_mode_toggled)
        private_row.addWidget(private_label)
        private_row.addWidget(self._private_toggle)
        header.addLayout(private_row)

        export_btn = QPushButton("Export", shell)
        export_btn.setObjectName("historyExportBtn")
        export_btn.setFont(settings_font(FONT_SMALL))
        export_btn.clicked.connect(self._export_json)
        header.addWidget(export_btn)

        close_btn = _CloseButton(shell)
        close_btn.clicked.connect(self.accept)
        header.addWidget(close_btn)
        shell_layout.addWidget(title_bar)

        self._search = _SearchField(shell)
        self._search.textChanged.connect(self._on_search_changed)
        shell_layout.addWidget(self._search)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self._date_combo = _DateCombo(shell)
        self._date_combo.setObjectName("historyDateFilter")
        self._date_combo.setFont(settings_font(FONT_SMALL))
        for label, _ in _DATE_RANGE_OPTIONS:
            self._date_combo.addItem(label)
        self._date_combo.currentIndexChanged.connect(self._apply_filters)

        self._project_combo = _ProjectCombo(shell)
        self._project_combo.setFont(settings_font(FONT_SMALL))
        self._project_combo.currentIndexChanged.connect(self._on_project_filter_changed)

        self._clear_filters_btn = QPushButton("Clear filters", shell)
        self._clear_filters_btn.setObjectName("clearFiltersBtn")
        self._clear_filters_btn.setFont(settings_font(FONT_CAPTION))
        self._clear_filters_btn.hide()
        self._clear_filters_btn.clicked.connect(self._clear_all_filters)

        filters.addWidget(self._date_combo)
        filters.addWidget(self._project_combo, stretch=1)
        filters.addWidget(self._clear_filters_btn)
        shell_layout.addLayout(filters)

        self._splitter = QSplitter(Qt.Orientation.Horizontal, shell)
        self._splitter.setObjectName("historySplitter")
        self._splitter.splitterMoved.connect(lambda *_: self._schedule_persist_geometry())

        list_panel = QWidget(self._splitter)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)

        self._list_stack = QStackedWidget(list_panel)
        self._list = QListView(self._list_stack)
        self._list.setObjectName("historyList")
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._list.setMouseTracking(True)
        self._list.viewport().setMouseTracking(True)
        self._list.setUniformItemSizes(True)
        self._list.setSpacing(0)
        self._list.setFrameShape(QFrame.Shape.NoFrame)

        self._model = HistoryListModel(self._list)
        self._list.setModel(self._model)
        self._delegate = HistoryRowDelegate(self._list)
        self._list.setItemDelegate(self._delegate)
        self._list.setMinimumHeight(self._delegate.row_height())

        QScroller.grabGesture(self._list.viewport(), QScroller.ScrollerGestureType.TouchGesture)

        self._list.entered.connect(self._on_row_hovered)
        self._list.clicked.connect(self._on_row_clicked)
        self._list.viewport().installEventFilter(self)
        self._list.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._delegate.copy_clicked.connect(self._copy_entry)
        self._delegate.restore_clicked.connect(self._restore_entry)
        self._delegate.delete_clicked.connect(self._delete_entry)

        self._empty_state = _EmptyStateWidget()
        self._list_stack.addWidget(self._list)
        self._list_stack.addWidget(self._empty_state)
        list_layout.addWidget(self._list_stack)
        self._splitter.addWidget(list_panel)

        detail_card = QFrame(self._splitter)
        detail_card.setObjectName("historyDetailCard")
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(16, 16, 16, 16)
        detail_layout.setSpacing(12)

        prompt_header = QHBoxLayout()
        prompt_label = QLabel("ORIGINAL PROMPT", detail_card)
        prompt_label.setObjectName("detailSectionLabel")
        prompt_label.setFont(settings_font(FONT_CAPTION, WEIGHT_MEDIUM))
        prompt_header.addWidget(prompt_label)
        prompt_header.addStretch()
        self._prompt_chevron = _ChevronButton(detail_card)
        self._prompt_chevron.clicked.connect(self._toggle_prompt_section)
        prompt_header.addWidget(self._prompt_chevron)
        detail_layout.addLayout(prompt_header)

        self._input_detail = _ContentSizedPromptEdit(detail_card)
        detail_layout.addWidget(self._input_detail)

        self._prompt_collapsed = QLabel("", detail_card)
        self._prompt_collapsed.setFont(settings_font(FONT_SMALL))
        self._prompt_collapsed.setStyleSheet(f"color: {TEXT_MUTED};")
        self._prompt_collapsed.hide()
        detail_layout.addWidget(self._prompt_collapsed)

        result_label = QLabel("OPTIMIZED RESULT", detail_card)
        result_label.setObjectName("detailSectionLabel")
        result_label.setFont(settings_font(FONT_CAPTION, WEIGHT_MEDIUM))
        detail_layout.addWidget(result_label)

        self._output_detail = QTextEdit(detail_card)
        self._output_detail.setObjectName("detailOutput")
        self._output_detail.setReadOnly(True)
        self._output_detail.setFont(settings_font(FONT_SMALL))
        self._apply_prose_line_height(self._output_detail)
        detail_layout.addWidget(self._output_detail, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._use_prompt_btn = QPushButton("Use prompt", detail_card)
        self._use_prompt_btn.setObjectName("detailBtnPrimary")
        self._use_prompt_btn.setFont(settings_font(FONT_SMALL, WEIGHT_MEDIUM))
        self._use_prompt_btn.clicked.connect(self._emit_use_prompt)
        btn_row.addWidget(self._use_prompt_btn)

        self._use_both_btn = QPushButton("Use both", detail_card)
        self._use_both_btn.setObjectName("detailBtnSecondary")
        self._use_both_btn.setFont(settings_font(FONT_SMALL))
        self._use_both_btn.clicked.connect(self._emit_use_both)
        btn_row.addWidget(self._use_both_btn)

        self._rerun_btn = QPushButton("Re-run", detail_card)
        self._rerun_btn.setObjectName("detailBtnSecondary")
        self._rerun_btn.setFont(settings_font(FONT_SMALL))
        self._rerun_btn.setToolTip("Run this prompt again")
        self._rerun_btn.clicked.connect(self._emit_rerun)
        btn_row.addWidget(self._rerun_btn)
        btn_row.addStretch()
        detail_layout.addLayout(btn_row)

        self._splitter.addWidget(detail_card)
        shell_layout.addWidget(self._splitter, stretch=1)

        self._detail_card = detail_card
        self._set_detail_visible(False)
        self._reload_project_combo()

    @staticmethod
    def _apply_prose_line_height(editor: QTextEdit) -> None:
        fmt = QTextBlockFormat()
        fmt.setLineHeight(
            155,
            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
        )
        cursor = QTextCursor(editor.document())
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.mergeBlockFormat(fmt)

    def _update_prompt_max_height(self) -> None:
        if not self._detail_card.isVisible():
            return
        cap = int(self._detail_card.height() * 0.4)
        self._input_detail.set_max_height(cap)

    def _set_detail_visible(self, visible: bool) -> None:
        self._detail_card.setVisible(visible)
        if visible:
            self._update_prompt_max_height()

    def _toggle_prompt_section(self) -> None:
        expanded = not self._input_detail.isVisible()
        self._input_detail.setVisible(expanded)
        self._prompt_collapsed.setVisible(not expanded)
        self._prompt_chevron.set_expanded(expanded)
        self._prompt_chevron.setToolTip("Collapse" if expanded else "Expand")

    def _update_collapsed_prompt(self, text: str) -> None:
        fm = QFontMetrics(self._prompt_collapsed.font())
        available = max(100, self._prompt_collapsed.width() or self._detail_card.width() - 48)
        elided = fm.elidedText(_collapse_whitespace(text), Qt.TextElideMode.ElideRight, available)
        self._prompt_collapsed.setText(elided)

    # --- Data loading ---

    def _start_load(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._load_worker = _HistoryLoadWorker(self)
        self._load_worker.loaded.connect(self._on_entries_loaded)
        self._load_worker.start()

    def _on_entries_loaded(self, entries: list[dict[str, Any]]) -> None:
        self._loading = False
        self._all_entries = [e for e in entries if not _entry_is_private(e)]
        self._search_index = []
        for entry in self._all_entries:
            blob = " ".join(
                [
                    str(entry.get("input") or ""),
                    str(entry.get("output") or ""),
                    str(entry.get("model") or ""),
                    str(entry.get("project_name") or ""),
                ]
            ).lower()
            self._search_index.append((entry, blob))
        self._reload_project_combo()
        self._apply_filters()

    def _reload_project_combo(self) -> None:
        current = self._project_filter
        self._project_combo.blockSignals(True)
        self._project_combo.clear()
        self._project_combo.addItem("All projects", "")
        for project in list_projects():
            name = str(project.get("name") or "").strip()
            if name:
                self._project_combo.addItem(name, name)
        if current:
            idx = self._project_combo.findData(current)
            self._project_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self._project_combo.setCurrentIndex(0)
        self._project_combo.blockSignals(False)

    # --- Filtering ---

    def _on_search_changed(self, _text: str) -> None:
        self._search_timer.start(SEARCH_DEBOUNCE_MS)

    def _on_project_filter_changed(self, _index: int) -> None:
        value = str(self._project_combo.currentData() or "").strip()
        self._project_filter = value or None
        self._apply_filters()

    def _date_range(self) -> tuple[date | None, date | None]:
        idx = self._date_combo.currentIndex()
        days = _DATE_RANGE_OPTIONS[idx][1]
        if days is None:
            return None, None
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=days - 1)
        return start, today

    def _has_active_filters(self) -> bool:
        return bool(self._search.text().strip()) or self._date_combo.currentIndex() > 0 or bool(
            self._project_filter
        )

    def _clear_all_filters(self) -> None:
        self._search.clear()
        self._date_combo.setCurrentIndex(0)
        self._project_combo.setCurrentIndex(0)
        self._project_filter = None
        self._apply_filters()

    def _apply_filters(self) -> None:
        if self._loading:
            return

        keyword = self._search.text().strip().lower()
        date_from, date_to = self._date_range()
        project_filter = (self._project_filter or "").strip().lower()

        dt_from: datetime | None = None
        if date_from is not None:
            dt_from = datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)
        dt_to: datetime | None = None
        if date_to is not None:
            dt_to = datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc)

        filtered: list[dict[str, Any]] = []
        for entry, blob in self._search_index:
            if project_filter:
                entry_project = str(entry.get("project_name") or "").strip().lower()
                if entry_project != project_filter:
                    continue
            ts_raw = str(entry.get("timestamp") or "")
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except ValueError:
                ts = None
            if dt_from and (ts is None or ts < dt_from):
                continue
            if dt_to and (ts is None or ts > dt_to):
                continue
            if keyword and keyword not in blob:
                continue
            filtered.append(entry)

        self._filtered_entries = filtered
        self._model.set_entries(filtered)
        self._update_count(len(filtered), len(self._all_entries))
        self._update_empty_state()
        self._clear_filters_btn.setVisible(self._has_active_filters())

        if filtered:
            self._list.setCurrentIndex(self._model.index(0, 0))
            self._set_detail_visible(True)
        else:
            self._selected_entry = None
            self._set_detail_visible(False)

    def _update_count(self, shown: int, total: int) -> None:
        if shown == total:
            suffix = "entry" if total == 1 else "entries"
            self._count_label.setText(f"{total} {suffix}")
        else:
            self._count_label.setText(f"{shown} of {total} entries")

    def _filter_constraint_text(self) -> str:
        parts: list[str] = []
        idx = self._date_combo.currentIndex()
        if idx > 0:
            parts.append(self._date_combo.currentText().lower())
        if self._project_filter:
            parts.append(f"for {self._project_filter}")
        keyword = self._search.text().strip()
        if keyword:
            parts.append(f'matching "{keyword}"')
        return " ".join(parts)

    def _update_empty_state(self) -> None:
        if self._filtered_entries:
            self._list_stack.setCurrentIndex(0)
            return
        self._list_stack.setCurrentIndex(1)
        if not self._all_entries:
            self._empty_state.set_state(
                headline="No history yet",
                body="Optimized prompts appear here",
            )
        else:
            constraint = self._filter_constraint_text()
            body = f"Nothing {constraint}".strip() if constraint else "Nothing matches your filters"
            self._empty_state.set_state(
                headline="No matches",
                body=body,
                show_clear=True,
                on_clear=self._clear_all_filters,
            )

    def eventFilter(self, source, event):  # noqa: N802
        if source is self._list.viewport():
            et = event.type()
            if et == event.Type.Leave:
                self._delegate.set_hover(-1, None)
                self._list.viewport().update()
            elif et == event.Type.MouseMove:
                pos = event.position().toPoint()
                index = self._list.indexAt(pos)
                if index.isValid():
                    row = index.row()
                    local_pos = pos - self._list.visualRect(index).topLeft()
                    action = self._delegate.hit_action(row, local_pos)
                    self._delegate.set_hover(row, action)
                else:
                    self._delegate.set_hover(-1, None)
                self._list.viewport().update()
        return super().eventFilter(source, event)

    # --- Selection & detail ---

    def _on_row_hovered(self, index: QModelIndex) -> None:
        self._delegate.set_hover(index.row(), None)
        self._list.viewport().update()

    def _on_row_clicked(self, index: QModelIndex) -> None:
        self._delegate.set_hover(index.row(), None)

    def _on_selection_changed(self) -> None:
        indexes = self._list.selectionModel().selectedIndexes()
        if not indexes:
            self._selected_entry = None
            self._set_detail_enabled(False)
            return
        entry = indexes[0].data(EntryRole)
        if not isinstance(entry, dict):
            return
        self._selected_entry = entry
        input_text = str(entry.get("input") or "")
        self._input_detail.setPlainText(input_text)
        self._update_collapsed_prompt(input_text)
        self._output_detail.setPlainText(str(entry.get("output") or ""))
        self._apply_prose_line_height(self._output_detail)
        self._update_prompt_max_height()
        self._set_detail_enabled(True)

    def _set_detail_enabled(self, enabled: bool) -> None:
        self._use_prompt_btn.setEnabled(enabled)
        self._use_both_btn.setEnabled(enabled)
        self._rerun_btn.setEnabled(enabled)

    # --- Row actions ---

    def _copy_entry(self, entry: dict[str, Any]) -> None:
        text = str(entry.get("output") or "")
        QGuiApplication.clipboard().setText(text)

    def _restore_entry(self, entry: dict[str, Any]) -> None:
        self.promptRestored.emit(str(entry.get("input") or ""))
        self.accept()

    def _delete_entry(self, entry: dict[str, Any]) -> None:
        entry_id = str(entry.get("id") or "")
        if not entry_id:
            return
        row = self._model.row_for_id(entry_id)
        if row < 0:
            return

        steps = 12
        interval = DELETE_FADE_MS // steps
        step = [0]

        def tick() -> None:
            step[0] += 1
            opacity = max(0.0, 1.0 - step[0] / steps)
            idx = self._model.index(row, 0)
            self._model.setData(idx, opacity, OpacityRole)
            if step[0] >= steps:
                timer.stop()
                if delete_entry(entry_id):
                    self._all_entries = [e for e in self._all_entries if str(e.get("id")) != entry_id]
                    self._search_index = [
                        (e, b) for e, b in self._search_index if str(e.get("id")) != entry_id
                    ]
                    self._apply_filters()

        timer = QTimer(self)
        timer.timeout.connect(tick)
        timer.start(interval)

    # --- Header actions ---

    def _on_private_mode_toggled(self, checked: bool) -> None:
        cfg = load_config()
        cfg["save_history"] = not checked
        save_config(cfg)

    def _export_json(self) -> None:
        src = history_file_path()
        if not src.exists():
            return
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Export history JSON",
            "history.json",
            "JSON files (*.json)",
        )
        if not dest:
            return
        try:
            with src.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                data = [e for e in data if not _entry_is_private(e)]
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
        except (json.JSONDecodeError, OSError):
            shutil.copyfile(src, dest)

    def _emit_use_prompt(self) -> None:
        if not self._selected_entry:
            return
        self.promptRestored.emit(str(self._selected_entry.get("input") or ""))
        self.accept()

    def _emit_use_both(self) -> None:
        if not self._selected_entry:
            return
        self.use_both_requested.emit(
            str(self._selected_entry.get("input") or ""),
            str(self._selected_entry.get("output") or ""),
        )
        self.accept()

    def _emit_rerun(self) -> None:
        if not self._selected_entry:
            return
        self.rerun_requested.emit(str(self._selected_entry.get("input") or ""))
        self.accept()

    # --- Keyboard ---

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._selected_entry and (
                self._list.hasFocus() or self.focusWidget() is self._list
            ):
                self._emit_use_prompt()
                event.accept()
                return
        if event.key() == Qt.Key.Key_Delete and self._selected_entry:
            self._delete_entry(self._selected_entry)
            event.accept()
            return
        super().keyPressEvent(event)
