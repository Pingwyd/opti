"""
Reusable, token-driven building blocks for the Opti settings window.

Every pane in settings_ui.py composes from these instead of writing bespoke
layout/QSS. Custom painting (ToggleSwitch, Stepper, nav icons) exists because
icon-font glyphs are unreliable across machines — see ui_theme.py's QSS for
the static styling these widgets rely on.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Callable

from PyQt6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui_theme import (
    BORDER,
    BORDER_CONTROL,
    BORDER_STRONG,
    BORDER_SUBTLE,
    CANVAS,
    CORAL,
    CORAL_ON,
    CORAL_TINT,
    DANGER,
    DANGER_BORDER,
    DANGER_TEXT,
    DANGER_TINT,
    DESIGN_TOKENS,
    FONT_BODY,
    FONT_CAPTION,
    FONT_MICRO,
    HOVER_TINT,
    INPUT_BG,
    SUCCESS,
    SURFACE_RAISED,
    TEXT_BODY,
    TEXT_DISABLED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TOGGLE_DISABLED_KNOB,
    WEIGHT_MEDIUM,
    project_color,
    settings_font,
    settings_mono_font,
)

PILL_PLACEHOLDER = DESIGN_TOKENS["copy"]["placeholder"]
PILL_FIRST_RUN_EXAMPLE = DESIGN_TOKENS["copy"]["first_run_example"]
PILL_CHAR_COUNT_THRESHOLD = 500
PILL_MAX_LINES = DESIGN_TOKENS["layout"].get("input_max_lines", 6)


# ---------------------------------------------------------------------------
# Input pill widgets (popup.py)
# ---------------------------------------------------------------------------


class SparkIcon(QWidget):
    """15px coral spark drawn with QPainter — no font glyphs."""

    SIZE = 15

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def sizeHint(self) -> QSize:
        return QSize(self.SIZE, self.SIZE)

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(CORAL))
        pen.setWidthF(1.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = self.width() / 2, self.height() / 2
        path = QPainterPath()
        for angle in range(0, 360, 72):
            rad = math.radians(angle)
            outer_x = cx + 5.5 * math.cos(rad)
            outer_y = cy + 5.5 * math.sin(rad)
            inner_rad = math.radians(angle + 36)
            inner_x = cx + 2.2 * math.cos(inner_rad)
            inner_y = cy + 2.2 * math.sin(inner_rad)
            if angle == 0:
                path.moveTo(outer_x, outer_y)
            else:
                path.lineTo(outer_x, outer_y)
            path.lineTo(inner_x, inner_y)
        path.closeSubpath()
        painter.drawPath(path)
        painter.end()


class GrowingTextEdit(QTextEdit):
    """Auto-growing prompt input: 1–6 lines, Ctrl/Cmd+Enter submits."""

    heightChanged = pyqtSignal(int)
    submitRequested = pyqtSignal()
    ghostDismissed = pyqtSignal()

    def __init__(
        self,
        *,
        max_lines: int = PILL_MAX_LINES,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("growingPromptInput")
        self._max_lines = max_lines
        self._showing_ghost = False
        self._ghost_text = ""
        self.setAcceptRichText(False)
        self.setFrameStyle(0)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        font = settings_font(DESIGN_TOKENS["font"]["size_base"])
        self.setFont(font)
        doc = self.document()
        doc.setDocumentMargin(2)
        doc.contentsChanged.connect(self._on_contents_changed)
        QTimer.singleShot(0, self._emit_height)

    def show_ghost_example(self, text: str) -> None:
        self._ghost_text = text
        self._showing_ghost = True
        self.setPlainText(text)
        ghost_font = settings_font(DESIGN_TOKENS["font"]["size_base"])
        ghost_font.setItalic(True)
        self.setFont(ghost_font)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_DISABLED))
        self.setPalette(palette)
        self._emit_height()

    def _dismiss_ghost(self) -> None:
        if not self._showing_ghost:
            return
        self._showing_ghost = False
        self._ghost_text = ""
        self.clear()
        self.setFont(settings_font(DESIGN_TOKENS["font"]["size_base"]))
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
        self.setPalette(palette)
        self.ghostDismissed.emit()

    def effective_text(self) -> str:
        if self._showing_ghost:
            return ""
        return self.toPlainText()

    def has_substantive_text(self) -> bool:
        return bool(self.effective_text().strip())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._showing_ghost and event.text():
            self._dismiss_ghost()
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            mods = event.modifiers()
            if mods & Qt.KeyboardModifier.ControlModifier or mods & Qt.KeyboardModifier.MetaModifier:
                self.submitRequested.emit()
                event.accept()
                return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if self._showing_ghost:
            self._dismiss_ghost()
        super().mousePressEvent(event)

    def focusInEvent(self, event) -> None:
        if self._showing_ghost:
            self._dismiss_ghost()
        super().focusInEvent(event)

    def _on_contents_changed(self) -> None:
        if self._showing_ghost:
            current = self.toPlainText()
            if current != self._ghost_text:
                self._dismiss_ghost()
        self._emit_height()

    def _line_height(self) -> int:
        fm = QFontMetrics(self.font())
        # height() includes descenders (y, p, g); lineSpacing() alone clips placeholders.
        return max(fm.lineSpacing(), fm.height())

    def _vertical_padding(self) -> int:
        """Extra viewport space so QTextEdit placeholder/ghost text isn't clipped."""
        return 6

    def _margins(self) -> int:
        doc_margin = int(self.document().documentMargin() * 2)
        frame = self.frameWidth() * 2
        return frame + doc_margin + self._vertical_padding()

    def _emit_height(self) -> None:
        doc = self.document()
        doc.setTextWidth(max(1, self.viewport().width()))
        layout = doc.documentLayout()
        content_h = int(layout.documentSize().height()) if layout else int(doc.size().height())
        one_line = self._line_height() + self._margins()
        max_h = self._max_lines * self._line_height() + self._margins()
        desired = max(one_line, min(content_h + self._margins(), max_h))
        needs_scroll = content_h + self._margins() > max_h
        policy = (
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if needs_scroll
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        if self.verticalScrollBarPolicy() != policy:
            self.setVerticalScrollBarPolicy(policy)
        if self.height() != desired:
            self.setFixedHeight(desired)
            self.heightChanged.emit(desired)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._emit_height()


class _ChevronMixin:
    """Draw a small chevron for selector chips."""

    _CHEVRON_W = 6
    _CHEVRON_H = 4

    def _paint_chevron(self, painter: QPainter, x: float, y: float, color: str) -> None:
        pen = QPen(QColor(color))
        pen.setWidthF(1.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        half_w = self._CHEVRON_W / 2
        painter.drawLine(QPointF(x, y), QPointF(x + half_w, y + self._CHEVRON_H))
        painter.drawLine(QPointF(x + half_w, y + self._CHEVRON_H), QPointF(x + self._CHEVRON_W, y))


class SelectorChip(QAbstractButton, _ChevronMixin):
    """Dropdown chip for project or mode selection."""

    def __init__(
        self,
        label: str,
        *,
        neutral: bool = True,
        project_name: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._label_text = label
        self._neutral = neutral
        self._project_name = project_name
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_metrics()

    def set_label(self, label: str) -> None:
        self._label_text = label
        self._apply_metrics()
        self.update()

    def set_project_name(self, name: str | None) -> None:
        self._project_name = name
        self._neutral = name is None or not name.strip()
        self.update()

    def _apply_metrics(self) -> None:
        font = settings_font(FONT_CAPTION)
        self.setFont(font)
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(self._label_text)
        chevron_gap = 6
        total_w = text_w + chevron_gap + self._CHEVRON_W + 18  # horizontal padding
        self.setFixedHeight(fm.height() + 8)
        self.setMinimumWidth(total_w)

    def sizeHint(self) -> QSize:
        return QSize(self.minimumWidth(), self.height())

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        if self._neutral:
            bg = QColor(INPUT_BG)
            fg = TEXT_SECONDARY
            border = BORDER_CONTROL
        else:
            fg_hex, _bg_rgba = project_color(self._project_name or "")
            bg = QColor(fg_hex)
            bg.setAlpha(40)
            fg = fg_hex
            border = BORDER_CONTROL
        painter.setPen(QPen(QColor(border)))
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 5, 5)
        fm = QFontMetrics(self.font())
        text_y = (self.height() + fm.ascent() - fm.descent()) / 2
        painter.setPen(QColor(fg))
        painter.setFont(self.font())
        painter.drawText(QRectF(9, 0, self.width() - 24, self.height()), Qt.AlignmentFlag.AlignVCenter, self._label_text)
        chevron_x = 9 + fm.horizontalAdvance(self._label_text) + 6
        chevron_y = (self.height() - self._CHEVRON_H) / 2
        self._paint_chevron(painter, chevron_x, chevron_y, fg if self._neutral else fg)
        painter.end()


class PrivateToggleChip(QAbstractButton):
    """Eye toggle — visually distinct from dropdown chips."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        font = settings_font(FONT_CAPTION)
        self.setFont(font)
        fm = QFontMetrics(font)
        self.setFixedHeight(fm.height() + 8)
        self.setMinimumWidth(fm.horizontalAdvance("Private") + 36)

    def set_checked_silent(self, checked: bool) -> None:
        self.blockSignals(True)
        self.setChecked(checked)
        self.blockSignals(False)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        checked = self.isChecked()
        if checked:
            painter.setBrush(QColor(CORAL_TINT))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 5, 5)
            fg = CORAL
        else:
            fg = TEXT_DISABLED
        icon_x = 4
        icon_y = self.height() / 2
        self._paint_eye(painter, icon_x, icon_y, fg, slashed=not checked)
        fm = QFontMetrics(self.font())
        text_x = 22
        painter.setPen(QColor(fg))
        painter.setFont(self.font())
        painter.drawText(
            QRectF(text_x, 0, self.width() - text_x, self.height()),
            Qt.AlignmentFlag.AlignVCenter,
            "Private",
        )
        painter.end()

    def _paint_eye(
        self, painter: QPainter, cx: float, cy: float, color: str, *, slashed: bool
    ) -> None:
        pen = QPen(QColor(color))
        pen.setWidthF(1.3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(cx - 6, cy)
        path.quadTo(cx, cy - 4, cx + 6, cy)
        path.quadTo(cx, cy + 4, cx - 6, cy)
        painter.drawPath(path)
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - 2, cy - 2, 4, 4))
        if slashed:
            pen = QPen(QColor(color))
            pen.setWidthF(1.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(cx - 5, cy + 4), QPointF(cx + 5, cy - 4))


class TransformActionButton(QWidget):
    """
    Split primary action: main area runs the transform; chevron opens mode menu.
    """

    runClicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("transformActionButton")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._main_btn = QPushButton(self)
        self._main_btn.setObjectName("pillOptimizeBtn")
        self._main_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._main_btn.setAccessibleName("Run transform")
        self._main_btn.clicked.connect(self.runClicked.emit)

        self._menu_btn = QPushButton("\u25be", self)
        self._menu_btn.setObjectName("pillOptimizeMenuBtn")
        self._menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._menu_btn.setAccessibleName("Choose transform mode")
        self._menu_btn.setFixedWidth(26)

        layout.addWidget(self._main_btn)
        layout.addWidget(self._menu_btn)

        self._has_text = False
        self._action_label = "Optimize"
        self._refresh_label()
        self._apply_inactive_state()

    def set_menu_clicked(self, handler: Callable[[], None]) -> None:
        self._menu_btn.clicked.connect(handler)

    def menu_anchor_global(self) -> QPoint:
        """Bottom-left corner of the chevron, for positioning a dropdown menu."""
        return self._menu_btn.mapToGlobal(QPoint(0, self._menu_btn.height()))

    def set_action_label(self, label: str) -> None:
        text = (label or "Optimize").strip() or "Optimize"
        if text == self._action_label:
            return
        self._action_label = text
        self._refresh_label()

    def set_has_text(self, has_text: bool) -> None:
        self._has_text = has_text
        self._apply_inactive_state()
        self._refresh_label()

    def set_tooltips(self, main_tip: str, menu_tip: str) -> None:
        self._main_btn.setToolTip(main_tip)
        self._menu_btn.setToolTip(menu_tip)

    def _apply_inactive_state(self) -> None:
        inactive = "false" if self._has_text else "true"
        for btn in (self._main_btn, self._menu_btn):
            btn.setProperty("inactive", inactive)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _refresh_label(self) -> None:
        hint = "Ctrl+↵"
        try:
            import sys

            if sys.platform == "darwin":
                hint = "⌘↵"
        except Exception:
            pass
        if self._has_text:
            self._main_btn.setText(f"{self._action_label}  {hint}")
        else:
            self._main_btn.setText(self._action_label)


class PrimaryButton(QPushButton):
    """Legacy single-button primary action (prefer TransformActionButton)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pillOptimizeBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("inactive", "true")
        self._has_text = False
        self._action_label = "Optimize"
        self._refresh_label()

    def set_action_label(self, label: str) -> None:
        text = (label or "Optimize").strip() or "Optimize"
        if text == self._action_label:
            return
        self._action_label = text
        self._refresh_label()

    def set_has_text(self, has_text: bool) -> None:
        self._has_text = has_text
        self.setProperty("inactive", "false" if has_text else "true")
        self.style().unpolish(self)
        self.style().polish(self)
        self._refresh_label()

    def _refresh_label(self) -> None:
        hint = "Ctrl+↵"
        try:
            import sys

            if sys.platform == "darwin":
                hint = "⌘↵"
        except Exception:
            pass
        if self._has_text:
            self.setText(f"{self._action_label}  {hint}")
        else:
            self.setText(self._action_label)


class PillIconButton(QAbstractButton):
    """Small icon-only button (history, settings)."""

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._kind = kind
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(28, 28)

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: ARG002
        color = TEXT_SECONDARY if self.underMouse() else TEXT_DISABLED
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color))
        pen.setWidthF(1.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = self.width() / 2, self.height() / 2
        if self._kind == "history":
            painter.drawEllipse(QRectF(cx - 5, cy - 5, 10, 10))
            painter.drawArc(QRectF(cx - 8, cy - 8, 16, 16), 90 * 16, 270 * 16)
            painter.drawLine(QPointF(cx, cy - 2), QPointF(cx, cy))
            painter.drawLine(QPointF(cx, cy), QPointF(cx + 3, cy + 2))
        elif self._kind == "settings":
            painter.drawEllipse(QRectF(cx - 4, cy - 4, 8, 8))
            for angle in range(0, 360, 45):
                rad = math.radians(angle)
                x1 = cx + 5.5 * math.cos(rad)
                y1 = cy + 5.5 * math.sin(rad)
                x2 = cx + 7.5 * math.cos(rad)
                y2 = cy + 7.5 * math.sin(rad)
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        elif self._kind == "crosshair":
            painter.drawLine(QPointF(cx - 6, cy), QPointF(cx + 6, cy))
            painter.drawLine(QPointF(cx, cy - 6), QPointF(cx, cy + 6))
            painter.drawEllipse(QRectF(cx - 3, cy - 3, 6, 6))
        painter.end()


class PillProgressBar(QWidget):
    """2px indeterminate progress line for optimization."""

    HEIGHT = 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)
        self._phase = 0.0
        self._state = "idle"  # idle | running | success | danger
        self._anim = QPropertyAnimation(self, b"phase", self)
        self._anim.setDuration(1200)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setLoopCount(-1)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)

    def _get_phase(self) -> float:
        return self._phase

    def _set_phase(self, value: float) -> None:
        self._phase = value
        self.update()

    phase = pyqtProperty(float, fget=_get_phase, fset=_set_phase)

    def start(self) -> None:
        self._state = "running"
        self.show()
        if self._anim.state() != QPropertyAnimation.State.Running:
            self._anim.start()

    def flash_success(self) -> None:
        self._state = "success"
        self._anim.stop()
        self.update()

    def flash_danger(self) -> None:
        self._state = "danger"
        self._anim.stop()
        self.update()

    def hide_bar(self) -> None:
        self._anim.stop()
        self._state = "idle"
        self.hide()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(BORDER))
        if self._state == "running":
            sweep_w = max(40, int(w * 0.25))
            x = int((w + sweep_w) * self._phase) - sweep_w
            painter.fillRect(x, 0, sweep_w, h, QColor(CORAL))
        elif self._state == "success":
            painter.fillRect(0, 0, w, h, QColor(SUCCESS))
        elif self._state == "danger":
            painter.fillRect(0, 0, w, h, QColor(DANGER))
        painter.end()


class CharCountLabel(QLabel):
    """Muted mono count, visible only past threshold."""

    def __init__(self, threshold: int = PILL_CHAR_COUNT_THRESHOLD, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pillCharCount")
        self._threshold = threshold
        self.setFont(settings_mono_font(FONT_MICRO))
        self.hide()

    def update_count(self, count: int) -> None:
        if count > self._threshold:
            self.setText(str(count))
            self.show()
        else:
            self.hide()


def pill_menu_stylesheet() -> str:
    return f"""
        QMenu {{
            background: {SURFACE_RAISED};
            color: {TEXT_BODY};
            border: 1px solid {BORDER_CONTROL};
            border-radius: 8px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px 6px 12px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background: {CORAL_TINT};
            color: {TEXT_PRIMARY};
        }}
    """


# ---------------------------------------------------------------------------
# SettingRow — the atomic unit of every pane
# ---------------------------------------------------------------------------


class SettingRow(QWidget):
    """
    [ label                              ] [ control ]
    [ helper text (optional, muted)      ]

    Height derives from QFontMetrics of the actual label/helper fonts, never
    a literal, so it scales correctly at 100/125/150% DPI and with longer
    translated strings.
    """

    CONTROL_WIDTH = 190
    CONTROL_WIDTH_WIDE = 280
    SHORTCUT_CONTROL_WIDTH = 240

    def __init__(
        self,
        label: str,
        helper: str = "",
        *,
        indent: bool = False,
        control_width: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingRow")
        self.setProperty("indent", "true" if indent else "false")
        self.setProperty("last", "false")
        self._control_width = control_width if control_width is not None else self.CONTROL_WIDTH

        outer = QHBoxLayout(self)
        outer.setContentsMargins(22 if indent else 0, 10, 0, 10)
        outer.setSpacing(16)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self._label = QLabel(label, self)
        self._label.setObjectName("settingRowLabel")
        self._label.setFont(settings_font(FONT_BODY))
        self._label.setWordWrap(True)
        text_col.addWidget(self._label)

        self._helper = QLabel(helper, self)
        self._helper.setObjectName("settingRowHelper")
        self._helper.setFont(settings_font(FONT_CAPTION))
        self._helper.setWordWrap(True)
        self._helper.setVisible(bool(helper))
        text_col.addWidget(self._helper)

        outer.addLayout(text_col, 1)

        self._control_box = QWidget(self)
        self._control_box.setObjectName("settingRowControl")
        self._control_box.setFixedWidth(self._control_width)
        self._control_box.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self._control_layout = QHBoxLayout(self._control_box)
        self._control_layout.setContentsMargins(0, 0, 0, 0)
        self._control_layout.setSpacing(6)
        outer.addWidget(self._control_box, 0)

        self._control: QWidget | None = None
        self._recompute_height()

    def set_control(self, widget: QWidget, *, stretch: bool = False) -> QWidget:
        """Place `widget` in the fixed-width right column, right-aligned.

        `stretch` widens the column to `CONTROL_WIDTH_WIDE` for controls that
        need more horizontal room (e.g. model-id text fields) than the
        standard column width comfortably fits.
        """
        if self._control is not None:
            self._control.setParent(None)
        self._control = widget
        widget.setParent(self._control_box)
        if stretch and self._control_width == self.CONTROL_WIDTH:
            self._control_width = self.CONTROL_WIDTH_WIDE
            self._control_box.setFixedWidth(self._control_width)
        if stretch:
            self._control_layout.addWidget(widget)
        else:
            align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            self._control_layout.addWidget(widget, 0, align)
        widget.setEnabled(self.isEnabled())
        self._recompute_height()
        return widget

    def control(self) -> QWidget | None:
        return self._control

    def label_widget(self) -> QLabel:
        return self._label

    def helper_widget(self) -> QLabel:
        return self._helper

    def set_helper_text(self, text: str, *, danger: bool = False, success: bool = False) -> None:
        self._helper.setText(text)
        self._helper.setVisible(bool(text))
        self._helper.setProperty("danger", "true" if danger else "false")
        self._helper.setProperty("success", "true" if success else "false")
        self._helper.style().unpolish(self._helper)
        self._helper.style().polish(self._helper)
        self._recompute_height()

    def set_last(self, is_last: bool) -> None:
        """Suppress the bottom hairline on the last row of a group."""
        self.setProperty("last", "true" if is_last else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 (Qt override)
        super().setEnabled(enabled)
        self._label.setProperty("disabled", "false" if enabled else "true")
        self._label.style().unpolish(self._label)
        self._label.style().polish(self._label)
        self._helper.setProperty("disabled", "false" if enabled else "true")
        self._helper.style().unpolish(self._helper)
        self._helper.style().polish(self._helper)
        if self._control is not None:
            self._control.setEnabled(enabled)

    def _recompute_height(self) -> None:
        fm_label = QFontMetrics(self._label.font())
        height = fm_label.height()
        if self._helper.isVisible() and self._helper.text():
            fm_helper = QFontMetrics(self._helper.font())
            height += 2 + fm_helper.height()
        text_total = height + 20  # top(10) + bottom(10) margins
        control_total = 40
        if self._control is not None:
            control_total = self._control.sizeHint().height() + 20
        self.setMinimumHeight(max(text_total, control_total, 40))


# ---------------------------------------------------------------------------
# ToggleSwitch — custom-painted pill, never a QCheckBox
# ---------------------------------------------------------------------------


class ToggleSwitch(QAbstractButton):
    """
    34x19 pill toggle. State is communicated by knob position, which cannot
    fail to render the way a checkbox's checkmark glyph can.
    """

    WIDTH = 34
    HEIGHT = 19
    KNOB_SIZE = 15
    MARGIN = 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self._knob_pos = 0.0
        self._anim = QPropertyAnimation(self, b"knobPos", self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate_to_state)

    def _animate_to_state(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._knob_pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def set_checked_silent(self, checked: bool) -> None:
        """Set state on initial load without animating or emitting `toggled`."""
        self.blockSignals(True)
        self.setChecked(checked)
        self.blockSignals(False)
        self._knob_pos = 1.0 if checked else 0.0
        self.update()

    def _get_knob_pos(self) -> float:
        return self._knob_pos

    def _set_knob_pos(self, value: float) -> None:
        self._knob_pos = value
        self.update()

    knobPos = pyqtProperty(float, fget=_get_knob_pos, fset=_set_knob_pos)

    def sizeHint(self) -> QSize:
        return QSize(self.WIDTH, self.HEIGHT)

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.isEnabled():
            track_color = QColor(BORDER_SUBTLE)
            knob_color = QColor(TOGGLE_DISABLED_KNOB)
        elif self.isChecked():
            track_color = QColor(CORAL)
            knob_color = QColor(CANVAS)
        else:
            track_color = QColor(BORDER_CONTROL)
            knob_color = QColor(TEXT_MUTED)

        radius = self.HEIGHT / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(QRectF(0, 0, self.WIDTH, self.HEIGHT), radius, radius)

        travel = self.WIDTH - self.MARGIN * 2 - self.KNOB_SIZE
        knob_x = self.MARGIN + travel * self._knob_pos
        knob_y = (self.HEIGHT - self.KNOB_SIZE) / 2
        painter.setBrush(knob_color)
        painter.drawEllipse(QRectF(knob_x, knob_y, self.KNOB_SIZE, self.KNOB_SIZE))
        painter.end()


# ---------------------------------------------------------------------------
# Stepper — replaces QSpinBox entirely
# ---------------------------------------------------------------------------


class _StepperButton(QAbstractButton):
    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._kind = kind  # "minus" | "plus"
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(26, 26)
        self.setAutoRepeat(True)
        self.setAutoRepeatDelay(400)
        self.setAutoRepeatInterval(80)

    def sizeHint(self) -> QSize:
        return QSize(26, 26)

    def enterEvent(self, event) -> None:  # noqa: ARG002
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: ARG002
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            color = BORDER_CONTROL
        elif self.underMouse():
            color = CORAL
        else:
            color = TEXT_BODY
        pen = QPen(QColor(color))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        cx, cy = self.width() / 2, self.height() / 2
        half = 4.5
        painter.drawLine(QPointF(cx - half, cy), QPointF(cx + half, cy))
        if self._kind == "plus":
            painter.drawLine(QPointF(cx, cy - half), QPointF(cx, cy + half))
        painter.end()


class Stepper(QWidget):
    """`[ - ] [ value ] [ + ]` numeric control. Glyphs are QPainter-drawn."""

    valueChanged = pyqtSignal(int)

    def __init__(
        self,
        minimum: int,
        maximum: int,
        step: int = 1,
        value: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("stepperContainer")
        self._min = minimum
        self._max = maximum
        self._step = step
        self._value = minimum if value is None else max(minimum, min(maximum, value))

        outer = QHBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)
        outer.setSpacing(0)

        self._minus = _StepperButton("minus", self)
        self._minus.clicked.connect(self._decrement)
        outer.addWidget(self._minus)

        self._value_label = QLabel(str(self._value), self)
        self._value_label.setFont(settings_mono_font(FONT_BODY, WEIGHT_MEDIUM))
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_label.setMinimumWidth(44)
        outer.addWidget(self._value_label, 1)

        self._plus = _StepperButton("plus", self)
        self._plus.clicked.connect(self._increment)
        outer.addWidget(self._plus)

        self.setStyleSheet(
            f"QWidget#stepperContainer {{ background: {INPUT_BG}; "
            f"border: 1px solid {BORDER_CONTROL}; border-radius: 7px; }}"
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocusProxy(self._minus)
        self._refresh()

    def value(self) -> int:
        return self._value

    def setValue(self, value: int, *, emit: bool = True) -> None:
        clamped = max(self._min, min(self._max, int(value)))
        if clamped == self._value:
            return
        self._value = clamped
        self._refresh()
        if emit:
            self.valueChanged.emit(self._value)

    def _decrement(self) -> None:
        self.setValue(self._value - self._step)

    def _increment(self) -> None:
        self.setValue(self._value + self._step)

    def _refresh(self) -> None:
        self._value_label.setText(str(self._value))
        self._minus.setEnabled(self.isEnabled() and self._value > self._min)
        self._plus.setEnabled(self.isEnabled() and self._value < self._max)

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        super().setEnabled(enabled)
        self._refresh()


# ---------------------------------------------------------------------------
# KeyCapRow — click-to-record shortcut editor for the Shortcuts pane
# ---------------------------------------------------------------------------


class KeyCapRow(QWidget):
    """
    Renders a binding as individual keycaps. Click to enter record mode;
    the next keypress captures the combo, Esc cancels.
    """

    sequence_changed = pyqtSignal(str)
    CAP_H_PAD = 8
    CAP_V_PAD = 4
    CAP_GAP = 4

    def __init__(
        self,
        initial_sequence: str,
        *,
        is_global: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("keyCapRow")
        self._sequence = initial_sequence
        self._is_global = is_global
        self._recording = False
        self._conflict = False
        self._conflict_reason = ""

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        outer.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._check = QLabel("\u2713", self)
        self._check.setObjectName("successCheck")
        self._check.setFont(settings_font(FONT_CAPTION, WEIGHT_MEDIUM))
        self._check.hide()
        outer.addWidget(self._check)

        self._host = QFrame(self)
        self._host.setObjectName("keyCapHost")
        self._host.setProperty("recording", "false")
        self._host_layout = QHBoxLayout(self._host)
        self._host_layout.setContentsMargins(0, 0, 0, 0)
        self._host_layout.setSpacing(self.CAP_GAP)
        self._host_layout.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        outer.addWidget(self._host)

        self._recording_label = QLabel("Press keys", self._host)
        self._recording_label.setObjectName("keyCapRecording")
        self._recording_label.setFont(settings_font(FONT_CAPTION, WEIGHT_MEDIUM))
        self._recording_label.setMinimumHeight(self._cap_height())
        self._recording_label.hide()
        self._host_layout.addWidget(self._recording_label)

        self._render_caps()

    def is_global(self) -> bool:
        return self._is_global

    def sequence(self) -> str:
        return self._sequence

    def set_sequence(self, sequence: str, *, emit: bool = False) -> None:
        self._sequence = sequence
        self._render_caps()
        if emit:
            self.sequence_changed.emit(self._sequence)

    def set_registered(self, registered: bool) -> None:
        self._check.setVisible(registered and not self._conflict and not self._recording)
        hint = self.sizeHint()
        self.setFixedSize(hint)

    def set_conflict(self, conflict: bool, reason: str = "") -> None:
        self._conflict = conflict
        self._conflict_reason = reason
        if conflict:
            self._check.hide()
        self._render_caps()

    def has_conflict(self) -> bool:
        return self._conflict

    def conflict_reason(self) -> str:
        return self._conflict_reason

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self._recording:
            self._enter_record_mode()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self._recording:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._exit_record_mode()
            return
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return
        modifiers = event.modifiers()
        seq_int = int(modifiers.value) | key
        seq = QKeySequence(seq_int).toString(QKeySequence.SequenceFormat.PortableText)
        self._exit_record_mode()
        if seq:
            self.set_sequence(seq, emit=True)

    def focusOutEvent(self, event) -> None:
        if self._recording:
            self._exit_record_mode()
        super().focusOutEvent(event)

    def _enter_record_mode(self) -> None:
        self._recording = True
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self._render_caps()

    def _exit_record_mode(self) -> None:
        self._recording = False
        self._render_caps()

    def _cap_height(self) -> int:
        return QFontMetrics(settings_mono_font(FONT_CAPTION)).height() + self.CAP_V_PAD * 2

    def _cap_style(self) -> str:
        if self._conflict:
            return (
                f"background: {DANGER_TINT}; border: 1px solid {DANGER_BORDER}; "
                f"border-radius: 4px; padding: {self.CAP_V_PAD}px {self.CAP_H_PAD}px; "
                f"color: {DANGER_TEXT};"
            )
        return (
            f"background: {INPUT_BG}; border: 1px solid {BORDER_CONTROL}; "
            f"border-radius: 4px; padding: {self.CAP_V_PAD}px {self.CAP_H_PAD}px; "
            f"color: {TEXT_BODY};"
        )

    def _cap_width_for(self, part: str) -> int:
        fm = QFontMetrics(settings_mono_font(FONT_CAPTION))
        return fm.horizontalAdvance(part) + self.CAP_H_PAD * 2 + 2

    def _content_width(self) -> int:
        if self._recording:
            fm = QFontMetrics(self._recording_label.font())
            return fm.horizontalAdvance("Press keys") + self.CAP_H_PAD * 2
        parts = [p for p in self._sequence.split("+") if p] if self._sequence else ["Unbound"]
        total = sum(self._cap_width_for(part) for part in parts)
        if len(parts) > 1:
            total += self.CAP_GAP * (len(parts) - 1)
        return max(total, 48)

    def sizeHint(self) -> QSize:
        height = self._cap_height() + 4
        width = self._content_width()
        if self._recording:
            width += 12  # host horizontal margins while recording
        if self._check.isVisible():
            width += self._check.sizeHint().width() + 6
        return QSize(width, height)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _clear_host(self) -> None:
        while self._host_layout.count():
            item = self._host_layout.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not self._recording_label:
                widget.deleteLater()

    def _render_caps(self) -> None:
        self._clear_host()
        self._host.setProperty("recording", "true" if self._recording else "false")
        self._host.style().unpolish(self._host)
        self._host.style().polish(self._host)

        if self._recording:
            self._check.hide()
            self._host_layout.setContentsMargins(6, 4, 6, 4)
            self._recording_label.show()
            self._host_layout.addWidget(self._recording_label)
        else:
            self._host_layout.setContentsMargins(0, 0, 0, 0)
            self._recording_label.hide()
            parts = [p for p in self._sequence.split("+") if p] if self._sequence else []
            if not parts:
                parts = ["Unbound"]
            for part in parts:
                cap = QLabel(part, self._host)
                cap.setObjectName("keyCap")
                cap.setProperty("conflict", "true" if self._conflict else "false")
                cap.setFont(settings_mono_font(FONT_CAPTION))
                cap.setStyleSheet(self._cap_style())
                cap.setFixedHeight(self._cap_height())
                cap.setFixedWidth(self._cap_width_for(part))
                cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._host_layout.addWidget(cap)

        hint = self.sizeHint()
        self.setFixedSize(hint)
        self._notify_row_resize()

    def _notify_row_resize(self) -> None:
        widget: QWidget | None = self.parentWidget()
        while widget is not None:
            if isinstance(widget, SettingRow):
                widget._recompute_height()
                break
            widget = widget.parentWidget()


# ---------------------------------------------------------------------------
# Badge — project name pill (stable color per name)
# ---------------------------------------------------------------------------


class Badge(QLabel):
    def __init__(self, project_name: str, parent: QWidget | None = None) -> None:
        super().__init__(project_name or "No project", parent)
        self.setObjectName("projectBadge")
        self.setFont(settings_font(FONT_CAPTION, WEIGHT_MEDIUM))
        fg, bg = project_color(project_name)
        self.setStyleSheet(
            f"QLabel#projectBadge {{ color: {fg}; background: {bg}; "
            f"border-radius: 4px; padding: 3px 9px; }}"
        )
        self.setMinimumHeight(QFontMetrics(self.font()).height() + 6)


# ---------------------------------------------------------------------------
# Sidebar nav icons — QPainter paths, never an icon font
# ---------------------------------------------------------------------------


def render_nav_icon(kind: str, color: str, size: int = 18) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if kind == "connection":
        painter.drawRoundedRect(QRectF(2.5, 6.5, 8, 5), 2.5, 2.5)
        painter.drawRoundedRect(QRectF(size - 10.5, 6.5, 8, 5), 2.5, 2.5)
        painter.drawLine(QPointF(size / 2 - 1.5, 9), QPointF(size / 2 + 1.5, 9))
    elif kind == "privacy":
        path = QPainterPath()
        path.moveTo(size / 2, 2.5)
        path.lineTo(size - 3.5, 5.5)
        path.lineTo(size - 3.5, size * 0.52)
        path.quadTo(size - 3.5, size - 3, size / 2, size - 1.5)
        path.quadTo(3.5, size - 3, 3.5, size * 0.52)
        path.lineTo(3.5, 5.5)
        path.closeSubpath()
        painter.drawPath(path)
    elif kind == "shortcuts":
        painter.drawRoundedRect(QRectF(2.5, 5.5, size - 5, size - 10), 2.5, 2.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        for cx, cy in ((6, 9), (9, 9), (12, 9), (15, 9), (7.5, 12.5), (13.5, 12.5)):
            painter.drawEllipse(QPointF(cx, cy), 0.9, 0.9)
    elif kind == "startup":
        painter.drawArc(QRectF(3, 4, size - 6, size - 6), -45 * 16, 270 * 16)
        painter.drawLine(QPointF(size / 2, 2.5), QPointF(size / 2, size / 2 - 1))
    elif kind == "projects":
        path = QPainterPath()
        path.moveTo(3, 6.5)
        path.lineTo(8, 6.5)
        path.lineTo(9.5, 8.5)
        path.lineTo(size - 3, 8.5)
        path.lineTo(size - 3, size - 4)
        path.lineTo(3, size - 4)
        path.closeSubpath()
        painter.drawPath(path)
    painter.end()
    return pm


def render_nav_pixmap(kind: str) -> QIcon:
    """QIcon with distinct Normal (muted) and Selected (coral) pixmaps."""
    icon = QIcon()
    icon.addPixmap(render_nav_icon(kind, TEXT_MUTED, 18), QIcon.Mode.Normal)
    icon.addPixmap(render_nav_icon(kind, CORAL, 18), QIcon.Mode.Selected)
    return icon


def render_close_icon(color: str, size: int = 14) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    margin = 4
    painter.drawLine(QPointF(margin, margin), QPointF(size - margin, size - margin))
    painter.drawLine(QPointF(size - margin, margin), QPointF(margin, size - margin))
    painter.end()
    return pm


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------


def format_relative_time(iso_timestamp: str) -> str:
    """Human-readable 'Saved N minutes ago' style string from an ISO timestamp."""
    if not iso_timestamp:
        return ""
    try:
        ts = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    seconds = max(0, int((datetime.now(timezone.utc) - ts).total_seconds()))

    if seconds < 60:
        return "Saved just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"Saved {minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"Saved {hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    if days < 30:
        return f"Saved {days} day{'s' if days != 1 else ''} ago"
    return f"Saved on {ts.strftime('%b %d, %Y')}"
