"""
Custom rate-limit dialog — matches Opti pill / settings styling (not native QMessageBox).
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QMouseEvent
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui_theme import (
    FONT_BODY,
    FONT_CAPTION,
    FONT_SMALL,
    WEIGHT_MEDIUM,
    rate_limit_dialog_stylesheet,
    settings_font,
)
from widgets import SparkIcon


class _DraggableDialogPanel(QFrame):
    """Dialog shell that can be dragged except over buttons."""

    def __init__(self, dialog: QDialog, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dialog = dialog
        self._drag_offset: QPoint | None = None

    def _interactive_child(self, child: QWidget | None) -> bool:
        widget: QWidget | None = child
        while widget is not None and widget is not self:
            if isinstance(widget, QPushButton):
                return True
            widget = widget.parentWidget()
        return False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._interactive_child(self.childAt(event.pos())):
                self._drag_offset = event.globalPosition().toPoint() - self._dialog.pos()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._dialog.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class RateLimitDialog(QDialog):
    """Ask whether to switch from Thorough to Fast after rate limiting."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setStyleSheet(rate_limit_dialog_stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)

        shell = _DraggableDialogPanel(self)
        shell.setObjectName("rateLimitDialogShell")
        shell.setCursor(Qt.CursorShape.SizeAllCursor)
        shadow = QGraphicsDropShadowEffect(shell)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 120))
        shell.setGraphicsEffect(shadow)

        layout = QVBoxLayout(shell)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(10)
        header.addWidget(SparkIcon(shell), 0, Qt.AlignmentFlag.AlignVCenter)

        title = QLabel("Rate limited", shell)
        title.setObjectName("rateLimitDialogTitle")
        title.setFont(settings_font(FONT_BODY, WEIGHT_MEDIUM))
        header.addWidget(title, 1, Qt.AlignmentFlag.AlignVCenter)

        close_btn = QPushButton("\u00d7", shell)
        close_btn.setObjectName("rateLimitCloseBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        body_row = QHBoxLayout()
        body_row.setSpacing(14)
        body_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        warning = QLabel("\u26a0", shell)
        warning.setObjectName("rateLimitDialogWarning")
        warning.setFont(settings_font(22))
        warning.setFixedWidth(28)
        warning.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        body_row.addWidget(warning)

        message = QLabel(
            "The API is temporarily busy in Thorough mode.\n\n"
            "Switch to Fast mode and retry? Fast uses your lighter model and "
            "often succeeds when the main model is rate limited.",
            shell,
        )
        message.setObjectName("rateLimitDialogBody")
        message.setFont(settings_font(FONT_CAPTION))
        message.setWordWrap(True)
        body_row.addWidget(message, 1)
        layout.addLayout(body_row)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addStretch(1)

        switch_btn = QPushButton("Switch to Fast", shell)
        switch_btn.setObjectName("rateLimitPrimaryBtn")
        switch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        switch_btn.setFont(settings_font(FONT_SMALL, WEIGHT_MEDIUM))
        switch_btn.clicked.connect(self.accept)
        switch_btn.setDefault(True)
        switch_btn.setAutoDefault(True)
        actions.addWidget(switch_btn)

        later_btn = QPushButton("Not now", shell)
        later_btn.setObjectName("rateLimitSecondaryBtn")
        later_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        later_btn.setFont(settings_font(FONT_SMALL))
        later_btn.clicked.connect(self.reject)
        actions.addWidget(later_btn)
        layout.addLayout(actions)

        root.addWidget(shell)
        self.setFixedWidth(440)
        self.adjustSize()
        self._center_on_parent(parent)

    def _center_on_parent(self, parent: QWidget | None) -> None:
        if parent is None:
            return
        parent_geo = parent.frameGeometry()
        x = parent_geo.center().x() - self.width() // 2
        y = parent_geo.center().y() - self.height() // 2
        self.move(x, y)

    @staticmethod
    def prompt_switch_to_fast(parent: QWidget | None = None) -> bool:
        """Return True when the user chooses Switch to Fast."""
        dialog = RateLimitDialog(parent)
        return dialog.exec() == QDialog.DialogCode.Accepted
