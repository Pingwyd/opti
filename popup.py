"""
PyQt6 popup window: show/hide, optimize worker, setup dialog.
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import Any, Callable, Literal, Optional

import pyperclip
from PyQt6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QKeySequence, QPainter, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from api import optimize_prompt_with_retry
from brand import APP_NAME
from config import (
    RESCUE_WINDOW_SHORTCUT,
    center_window_on_screen,
    get_active_model,
    get_auto_copy_clipboard,
    get_auto_inject_enabled,
    get_first_run_complete,
    get_pill_collapsed,
    get_private_session,
    get_shortcut_collapse,
    get_shortcut_hide_tray,
    get_shortcut_private,
    get_voice_enabled,
    get_voice_model_size,
    get_voice_ptt_shortcut,
    get_voice_recording_mode,
    get_voice_toggle_max_seconds,
    get_voice_transcription_mode,
    get_window_position,
    has_api_key,
    key_sequence_from_string,
    load_config,
    set_first_run_complete,
    set_mode,
    set_pill_collapsed,
    set_private_session,
    set_window_position,
    screen_for_window,
    validate_window_position as validate_window_coords,
)
from draft import clear_draft, load_draft, save_draft
from history import add_entry
from inject import (
    INJECT_DEFER_MS,
    can_inject_target,
    inject_via_paste,
    is_blocked_target,
    is_target_valid,
)
from projects import get_active_project, list_projects, set_active_project
from settings_ui import SettingsDialog
from ui_theme import C, DESIGN_TOKENS, L, popup_stylesheet
from widgets import (
    CharCountLabel,
    GrowingTextEdit,
    PILL_FIRST_RUN_EXAMPLE,
    PILL_PLACEHOLDER,
    PillIconButton,
    PillProgressBar,
    PrimaryButton,
    PrivateToggleChip,
    SelectorChip,
    SparkIcon,
    pill_menu_stylesheet,
)
from voice import AudioRecorder, VoiceTranscriber, missing_voice_deps_message, voice_deps_available

# Backward-compatible alias for first-run setup flow.
SetupDialog = SettingsDialog

log = logging.getLogger(__name__)

WINDOW_WIDTH = L["window_width"]
WINDOW_MIN_WIDTH = L.get("window_min_width", 560)
PILL_HEIGHT = L["pill_height"]
CHIP_SIZE = L["chip_size"]
INPUT_MIN_HEIGHT = L["input_min_height"]
INPUT_MAX_HEIGHT = L["input_max_height"]
RESULT_MIN_HEIGHT = L["result_min_height"]
ROOT_MARGIN = 8
ROOT_VERTICAL_MARGIN = ROOT_MARGIN * 2
PILL_LAYOUT_MARGINS = (14, 14, 16, 14)
PILL_LAYOUT_SPACING = 13
PROGRESS_HEIGHT = PillProgressBar.HEIGHT
CHIP_WINDOW_SIZE = CHIP_SIZE + ROOT_VERTICAL_MARGIN
_QT_WIDGETSIZE_MAX = 16777215
VoiceState = Literal["idle", "recording", "transcribing"]


def _play_voice_beep() -> None:
    if sys.platform == "win32":
        try:
            import winsound

            winsound.Beep(880, 60)
        except Exception:
            pass


class AudioLevelMeter(QWidget):
    """Simple RMS level meter shown while recording."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("audioLevelMeter")
        self.setFixedSize(44, 18)
        self._level = 0.0

    def set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, float(level) * 10.0))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001, N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bar_count = 5
        gap = 2
        width = self.width()
        height = self.height()
        bar_w = max(3, (width - gap * (bar_count - 1)) // bar_count)
        for index in range(bar_count):
            threshold = (index + 1) / bar_count
            active = self._level >= threshold * 0.85
            color = QColor(C["danger"] if active else C["text_muted"])
            color.setAlpha(220 if active else 90)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            bar_h = int(height * (0.35 + 0.65 * ((index + 1) / bar_count)))
            x = index * (bar_w + gap)
            y = height - bar_h
            painter.drawRoundedRect(x, y, bar_w, bar_h, 2, 2)
        painter.end()
        super().paintEvent(event)


class VoiceMicButton(QPushButton):
    """Mic control with explicit press/release for push-to-talk."""

    pressed_hold = pyqtSignal()
    released_hold = pyqtSignal()

    def mousePressEvent(self, event) -> None:  # noqa: ANN001, N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed_hold.emit()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001, N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.released_hold.emit()
        super().mouseReleaseEvent(event)


class TranscribeWorker(QThread):
    """Run local voice transcription off the UI thread."""

    finished = pyqtSignal(dict)
    download_progress = pyqtSignal(int, int)

    def __init__(self, audio: Any, *, model_size: str) -> None:
        super().__init__()
        self._audio = audio
        self._model_size = model_size

    def run(self) -> None:
        payload: dict[str, Any]
        try:
            transcriber = VoiceTranscriber(
                model_size=self._model_size,
                on_download_progress=lambda current, total: self.download_progress.emit(
                    current, total
                ),
            )
            text = transcriber.transcribe(self._audio)
            payload = {"ok": True, "text": text}
        except Exception as exc:  # noqa: BLE001
            log.exception("Transcribe worker failed")
            payload = {"ok": False, "error": str(exc)}
        self.finished.emit(payload)


class _InputKeyFilter(QObject):
    """Updates pill focus state when the prompt input gains or loses focus."""

    def __init__(self, pill: "PillBar", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pill = pill

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        try:
            evt_type = event.type()
        except Exception:
            return False

        if evt_type == QEvent.Type.FocusIn:
            self._pill.set_focused(True)
        elif evt_type == QEvent.Type.FocusOut:
            self._pill.set_focused(False)
        return False


class _VoiceKeyFilter(QObject):
    """Push-to-talk / toggle voice shortcuts while the popup is focused."""

    def __init__(self, window: "MetaPromptWindow", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window = window

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if not isinstance(event, QKeyEvent):
            return False
        try:
            evt_type = event.type()
        except Exception:
            return False
            
        if evt_type == QEvent.Type.KeyPress:
            if self._window._handle_voice_key_press(event):
                return True
        elif evt_type == QEvent.Type.KeyRelease:
            if self._window._handle_voice_key_release(event):
                return True
        return False


class OptimizeWorker(QThread):
    """Run optimize_prompt off the UI thread."""

    finished = pyqtSignal(dict)
    progress = pyqtSignal(str)

    def __init__(
        self,
        text: str,
        *,
        skip_history: bool = False,
        private_mode: bool = False,
    ) -> None:
        super().__init__()
        self._text = text
        self._skip_history = skip_history
        self._private_mode = private_mode
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self.requestInterruption()

    def run(self) -> None:
        if self._cancelled or self.isInterruptionRequested():
            self.finished.emit({"ok": False, "cancelled": True})
            return
        payload: dict[str, Any]
        try:
            model = get_active_model()

            def on_retry(attempt: int, max_attempts: int) -> None:
                if self._cancelled or self.isInterruptionRequested():
                    return
                self.progress.emit(f"Retrying… ({attempt}/{max_attempts})")

            result = optimize_prompt_with_retry(
                self._text,
                on_retry=on_retry,
                private_mode=self._private_mode,
                should_cancel=lambda: self._cancelled or self.isInterruptionRequested(),
            )
            if self._cancelled or self.isInterruptionRequested():
                self.finished.emit({"ok": False, "cancelled": True})
                return
            copied = False
            if get_auto_copy_clipboard():
                try:
                    pyperclip.copy(result)
                    copied = True
                except Exception:
                    log.warning("Clipboard copy failed after optimize", exc_info=True)
            if not self._skip_history:
                try:
                    active = get_active_project()
                    project_name = active.get("name") if active else None
                    add_entry(
                        self._text,
                        result,
                        model,
                        project_name=project_name,
                    )
                except Exception:
                    log.warning("Failed to save history entry", exc_info=True)
            payload = {"ok": True, "result": result, "copied": copied}
        except Exception as exc:  # noqa: BLE001
            if self._cancelled or self.isInterruptionRequested():
                self.finished.emit({"ok": False, "cancelled": True})
                return
            log.exception("Optimize worker failed")
            payload = {"ok": False, "error": str(exc)}
        self.finished.emit(payload)


class PillBar(QFrame):
    """Rounded input bar, draggable except over the text field."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pillBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(PILL_HEIGHT)
        self._drag_pos: QPoint | None = None
        self._press_global: QPoint | None = None
        self._window: MetaPromptWindow | None = None
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def set_host_window(self, window: "MetaPromptWindow") -> None:
        self._window = window

    def set_focused(self, focused: bool) -> None:
        self.setProperty("focused", "true" if focused else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_hovered(self, hovered: bool) -> None:
        self.setProperty("hovered", "true" if hovered else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def enterEvent(self, event) -> None:  # noqa: ANN001, N802
        self.set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001, N802
        self.set_hovered(False)
        super().leaveEvent(event)

    def _is_collapsed(self) -> bool:
        return self._window is not None and self._window.is_pill_collapsed()

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        if not self._is_collapsed():
            child = self.childAt(event.pos())
            if child is not None:
                w: QWidget | None = child
                while w is not None and w is not self:
                    if isinstance(w, (QLineEdit, QTextEdit, QPushButton, GrowingTextEdit, SelectorChip, PrivateToggleChip, PrimaryButton, PillIconButton)):
                        super().mousePressEvent(event)
                        return
                    w = w.parentWidget()
        if self._window is not None:
            global_pos = event.globalPosition().toPoint()
            self._press_global = global_pos
            self._drag_pos = global_pos - self._window.frameGeometry().topLeft()
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        if (
            self._drag_pos is not None
            and self._window is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._is_collapsed()
            and self._press_global is not None
            and self._window is not None
        ):
            delta = event.globalPosition().toPoint() - self._press_global
            if delta.manhattanLength() <= 6:
                self._window.expand()
                event.accept()
                self._drag_pos = None
                self._press_global = None
                return
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._window is not None
            and self._drag_pos is not None
        ):
            self._window._persist_window_position()
        self._drag_pos = None
        self._press_global = None
        super().mouseReleaseEvent(event)


CollapseGlobalAction = Literal["show_chip", "expand", "collapse"]


def collapse_global_action(*, is_visible: bool, is_collapsed: bool) -> CollapseGlobalAction:
    """
    Next action for the global collapse hotkey.

    Hidden → show as chip; visible chip → expand; visible expanded → collapse.
    """
    if not is_visible:
        return "show_chip"
    if is_collapsed:
        return "expand"
    return "collapse"


class MetaPromptWindow(QWidget):
    """Frameless, always-on-top floating popup."""

    def __init__(self, controller: "PopupController") -> None:
        super().__init__()
        self._controller = controller
        self._visible = False
        self._result_expanded = False
        self._pill_collapsed = False
        self._busy = False
        self._private_mode = get_private_session()
        self._expanded_geometry: tuple[int, int, int, int] | None = None
        self._worker: OptimizeWorker | None = None
        self._last_optimized_input: str | None = None
        self._session_has_optimization_result = False
        self._pending_optimize_text = ""
        self._status_error_opens_settings = False

        self._collapse_key_seq = QKeySequence()
        self._hide_key_seq = QKeySequence()
        self._private_key_seq = QKeySequence()
        self._collapse_shortcut: QShortcut | None = None
        self._hide_shortcut: QShortcut | None = None
        self._private_shortcut: QShortcut | None = None
        self._rescue_shortcut: QShortcut | None = None

        self._voice_state: VoiceState = "idle"
        self._voice_recorder: AudioRecorder | None = None
        self._voice_worker: TranscribeWorker | None = None
        self._voice_ptt_key_seq = QKeySequence()
        self._voice_ptt_keyboard_held = False
        self._voice_toggle_timer = QTimer(self)
        self._voice_toggle_timer.setSingleShot(True)
        self._voice_toggle_timer.timeout.connect(self._on_voice_toggle_timeout)
        self._voice_pulse_timer = QTimer(self)
        self._voice_pulse_timer.timeout.connect(self._tick_voice_pulse)
        self._voice_pulse_on = False

        self._draft_save_timer = QTimer(self)
        self._draft_save_timer.setSingleShot(True)
        self._draft_save_timer.timeout.connect(self._persist_draft)

        self._position_save_timer = QTimer(self)
        self._position_save_timer.setSingleShot(True)
        self._position_save_timer.timeout.connect(self._persist_window_position)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(WINDOW_MIN_WIDTH)
        self.setFixedWidth(WINDOW_WIDTH)
        self.setMaximumWidth(WINDOW_WIDTH)
        self.resize(WINDOW_WIDTH, PILL_HEIGHT + ROOT_VERTICAL_MARGIN)
        try:
            from main import app_icon

            self.setWindowIcon(app_icon())
        except Exception:
            pass

        self._progress_fade_timer = QTimer(self)
        self._progress_fade_timer.setSingleShot(True)
        self._progress_fade_timer.timeout.connect(self._hide_progress_bar)

        self._build_ui()
        self._apply_styles()
        self._setup_shortcuts()
        self._restore_draft_if_needed()
        self.hide()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(0)

        # --- Pill input bar ---
        print("TRACE: pillbar", flush=True)
        self._pill = PillBar(self)
        self._pill.set_host_window(self)
        print("TRACE: pillbar done", flush=True)

        pill_layout = QVBoxLayout(self._pill)
        pill_layout.setContentsMargins(*PILL_LAYOUT_MARGINS)
        pill_layout.setSpacing(PILL_LAYOUT_SPACING)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        input_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        print("TRACE: sparkicon", flush=True)
        self._pill_icon = SparkIcon(self._pill)
        input_row.addWidget(self._pill_icon, 0, Qt.AlignmentFlag.AlignTop)
        print("TRACE: sparkicon done, growingtextedit next", flush=True)

        self._input = GrowingTextEdit(parent=self._pill)
        print("TRACE: growingtextedit done", flush=True)
        self._input.setPlaceholderText(PILL_PLACEHOLDER)
        print("TRACE: placeholder set", flush=True)
        self._input.setAccessibleName("Prompt input")
        self._input.submitRequested.connect(self._submit)
        self._input.heightChanged.connect(lambda _h: self._resize_input())
        self._input.textChanged.connect(self._on_input_changed)
        self._input.ghostDismissed.connect(self._on_ghost_dismissed)
        print("TRACE: signals connected", flush=True)
        self._input_filter = _InputKeyFilter(self._pill, self._input)
        self._input.installEventFilter(self._input_filter)
        print("TRACE: event filter installed", flush=True)
        input_row.addWidget(self._input, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        print("TRACE: input added to layout", flush=True)

        print("TRACE: before audiolevelmeter", flush=True)
        self._voice_level_meter = AudioLevelMeter(self._pill)
        print("TRACE: audiolevelmeter constructed", flush=True)
        self._voice_level_meter.hide()
        input_row.addWidget(self._voice_level_meter, 0, Qt.AlignmentFlag.AlignTop)
        print("TRACE: audiolevelmeter added", flush=True)

        self._voice_status = QLabel("", self._pill)
        self._voice_status.setObjectName("voiceStatusLabel")
        self._voice_status.hide()
        input_row.addWidget(self._voice_status, 0, Qt.AlignmentFlag.AlignTop)
        print("TRACE: voice status added", flush=True)

        self._mic_btn = VoiceMicButton("\U0001f3a4", self._pill)
        print("TRACE: mic btn constructed", flush=True)
        self._mic_btn.setObjectName("voiceMicBtn")
        print("TRACE: mic btn objectname", flush=True)
        self._mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        print("TRACE: mic btn cursor", flush=True)
        self._mic_btn.setAccessibleName("Voice input")
        self._mic_btn.setToolTip("Hold to speak (push-to-talk)")
        print("TRACE: mic btn tooltip", flush=True)
        self._mic_btn.pressed_hold.connect(self._on_mic_pressed)
        self._mic_btn.released_hold.connect(self._on_mic_released)
        print("TRACE: mic btn signals", flush=True)
        self._mic_btn.hide()
        print("TRACE: mic btn hidden", flush=True)
        input_row.addWidget(self._mic_btn, 0, Qt.AlignmentFlag.AlignTop)
        print("TRACE: mic btn added", flush=True)

        pill_layout.addLayout(input_row)
        print("TRACE: input_row added to pill_layout", flush=True)

        self._progress_bar = PillProgressBar(self._pill)
        print("TRACE: progress bar constructed", flush=True)
        self._progress_bar.hide()
        pill_layout.addWidget(self._progress_bar)
        print("TRACE: progress bar added", flush=True)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)
        controls_row.setContentsMargins(0, 0, 0, 0)

        print("TRACE: before project chip", flush=True)
        self._project_chip = SelectorChip("No project", neutral=True, parent=self._pill)
        print("TRACE: project chip constructed", flush=True)
        self._project_chip.setToolTip("Active project context")
        self._project_chip.clicked.connect(self._show_project_menu)
        controls_row.addWidget(self._project_chip, 0, Qt.AlignmentFlag.AlignVCenter)
        print("TRACE: project chip added", flush=True)

        self._mode_chip = SelectorChip("Thorough", neutral=True, parent=self._pill)
        print("TRACE: mode chip constructed", flush=True)
        self._mode_chip.setAccessibleName("Toggle mode")
        print("TRACE: mode chip accessiblename", flush=True)
        self._mode_chip.clicked.connect(self._show_mode_menu)
        print("TRACE: mode chip connected", flush=True)
        controls_row.addWidget(self._mode_chip, 0, Qt.AlignmentFlag.AlignVCenter)
        print("TRACE: mode chip added", flush=True)

        self._private_chip = PrivateToggleChip(self._pill)
        print("TRACE: private chip constructed", flush=True)
        self._private_chip.setAccessibleName("Private session")
        self._private_chip.set_checked_silent(self._private_mode)
        self._private_chip.toggled.connect(self._set_private_mode)
        controls_row.addWidget(self._private_chip, 0, Qt.AlignmentFlag.AlignVCenter)

        controls_row.addStretch(1)

        self._char_count = CharCountLabel(parent=self._pill)
        controls_row.addWidget(self._char_count, 0, Qt.AlignmentFlag.AlignVCenter)

        self._history_btn = PillIconButton("history", self._pill)
        self._history_btn.setToolTip("History")
        self._history_btn.setAccessibleName("Open history")
        self._history_btn.clicked.connect(lambda: self._controller.show_history())
        controls_row.addWidget(self._history_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._settings_btn = PillIconButton("settings", self._pill)
        self._settings_btn.setToolTip("Settings")
        self._settings_btn.setAccessibleName("Open settings")
        self._settings_btn.clicked.connect(self._open_settings)
        controls_row.addWidget(self._settings_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._optimize_btn = PrimaryButton(self._pill)
        self._optimize_btn.clicked.connect(self._on_optimize_clicked)
        controls_row.addWidget(self._optimize_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._controls_row = QWidget(self._pill)
        self._controls_row.setLayout(controls_row)
        pill_layout.addWidget(self._controls_row)

        optimizing_row = QHBoxLayout()
        optimizing_row.setSpacing(8)
        optimizing_row.setContentsMargins(0, 0, 0, 0)
        self._pill_status = QLabel("", self._pill)
        self._pill_status.setObjectName("pillStatusLabel")
        optimizing_row.addWidget(self._pill_status, stretch=1)
        self._settings_link_btn = QPushButton("Open settings", self._pill)
        self._settings_link_btn.setObjectName("pillLinkBtn")
        self._settings_link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_link_btn.clicked.connect(self._open_settings)
        self._settings_link_btn.hide()
        optimizing_row.addWidget(self._settings_link_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self._cancel_btn = QPushButton("Cancel", self._pill)
        self._cancel_btn.setObjectName("pillCancelBtn")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._cancel_optimize)
        optimizing_row.addWidget(self._cancel_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self._optimizing_row = QWidget(self._pill)
        self._optimizing_row.setLayout(optimizing_row)
        self._optimizing_row.hide()
        pill_layout.addWidget(self._optimizing_row)

        self._refresh_project_selector()
        self._update_mode_chip()
        self._update_control_tooltips()
        self._sync_optimize_button()
        self._voice_key_filter = _VoiceKeyFilter(self)
        self.installEventFilter(self._voice_key_filter)
        self._input.installEventFilter(self._voice_key_filter)

        self._pill.customContextMenuRequested.connect(self._show_pill_menu)
        self._maybe_show_first_run_example()

        root.addWidget(self._pill)

        # --- Result panel (hidden until expand) ---
        self._result_frame = QFrame(self)
        self._result_frame.setObjectName("resultFrame")
        self._result_frame.hide()

        result_shadow = QGraphicsDropShadowEffect(self._result_frame)
        result_shadow.setBlurRadius(20)
        result_shadow.setOffset(0, 4)
        result_shadow.setColor(QColor(0, 0, 0, 80))
        self._result_frame.setGraphicsEffect(result_shadow)

        result_layout = QVBoxLayout(self._result_frame)
        result_layout.setContentsMargins(16, 12, 16, 12)
        result_layout.setSpacing(8)

        header = QHBoxLayout()
        self._status_label = QLabel("", self._result_frame)
        self._status_label.setObjectName("statusLabel")
        header.addWidget(self._status_label, stretch=1)

        copy_btn = QPushButton("Copy", self._result_frame)
        copy_btn.setObjectName("ghostBtn")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._copy_result)
        header.addWidget(copy_btn)

        collapse_btn = QPushButton("Collapse", self._result_frame)
        collapse_btn.setObjectName("ghostBtn")
        collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        collapse_btn.clicked.connect(lambda: self.collapse_result(reset_ui=False))
        header.addWidget(collapse_btn)

        result_layout.addLayout(header)

        self._result_text = QTextEdit(self._result_frame)
        self._result_text.setObjectName("resultText")
        self._result_text.setReadOnly(False)
        self._result_text.setMinimumHeight(RESULT_MIN_HEIGHT - 60)
        result_layout.addWidget(self._result_text)

        self._inject_row = QWidget(self._result_frame)
        self._inject_row.setObjectName("injectRow")
        inject_layout = QHBoxLayout(self._inject_row)
        inject_layout.setContentsMargins(0, 0, 0, 0)
        inject_layout.setSpacing(8)
        self._inject_label = QLabel("", self._inject_row)
        self._inject_label.setObjectName("injectLabel")
        self._inject_btn = QPushButton("Inject", self._inject_row)
        self._inject_btn.setObjectName("injectBtn")
        self._inject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._inject_btn.clicked.connect(self._on_inject_clicked)
        inject_layout.addWidget(self._inject_label, stretch=1)
        inject_layout.addWidget(self._inject_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self._inject_row.hide()
        result_layout.addWidget(self._inject_row)

        root.addWidget(self._result_frame)

        self._resize_compact()

    def _apply_styles(self) -> None:
        self.setStyleSheet(popup_stylesheet())
        font = QFont("Segoe UI", 10)
        self.setFont(font)

    def _setup_shortcuts(self) -> None:
        self.reload_shortcuts()

    def reload_shortcuts(self) -> None:
        """Reload popup shortcuts from config.json (call after settings save)."""
        if self._collapse_shortcut is not None:
            self._collapse_shortcut.deleteLater()
            self._collapse_shortcut = None
        if self._hide_shortcut is not None:
            self._hide_shortcut.deleteLater()
            self._hide_shortcut = None
        if self._private_shortcut is not None:
            self._private_shortcut.deleteLater()
            self._private_shortcut = None
        if self._rescue_shortcut is not None:
            self._rescue_shortcut.deleteLater()
            self._rescue_shortcut = None

        self._collapse_key_seq = key_sequence_from_string(get_shortcut_collapse())
        self._hide_key_seq = key_sequence_from_string(get_shortcut_hide_tray())
        self._private_key_seq = key_sequence_from_string(get_shortcut_private())

        if not self._collapse_key_seq.isEmpty():
            collapse = QShortcut(self._collapse_key_seq, self)
            collapse.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            collapse.activated.connect(self.toggle_pill_collapse)
            self._collapse_shortcut = collapse

        if not self._hide_key_seq.isEmpty():
            hide = QShortcut(self._hide_key_seq, self)
            hide.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            hide.activated.connect(self.hide_popup)
            self._hide_shortcut = hide

        if not self._private_key_seq.isEmpty():
            private = QShortcut(self._private_key_seq, self)
            private.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            private.activated.connect(self._toggle_private_mode)
            self._private_shortcut = private

        self._update_control_tooltips()

        rescue_seq = key_sequence_from_string(RESCUE_WINDOW_SHORTCUT)
        if not rescue_seq.isEmpty():
            rescue = QShortcut(rescue_seq, self)
            rescue.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            rescue.activated.connect(self.reset_window_position)
            self._rescue_shortcut = rescue

        self._reload_voice_settings()

    def _reload_voice_settings(self) -> None:
        """Refresh voice UI from config (call after settings save)."""
        self._voice_ptt_key_seq = key_sequence_from_string(get_voice_ptt_shortcut())
        enabled = get_voice_enabled()
        self._mic_btn.setVisible(enabled)
        if not enabled:
            self._stop_voice_recording(silent=True)
            self._cancel_voice_transcription()
        mode = get_voice_recording_mode()
        ptt_hint = self._shortcut_hint(self._voice_ptt_key_seq)
        if mode == "toggle":
            self._mic_btn.setToolTip(
                f"Click to start/stop recording{ptt_hint}"
            )
        else:
            self._mic_btn.setToolTip(
                f"Hold to speak, or hold {get_voice_ptt_shortcut()} while focused{ptt_hint}"
            )
        if enabled and not voice_deps_available():
            self._mic_btn.setEnabled(False)
            self._mic_btn.setToolTip(missing_voice_deps_message())
        else:
            self._mic_btn.setEnabled(True)
        self._update_voice_ui()

    def _voice_can_start(self) -> bool:
        return (
            get_voice_enabled()
            and not self._busy
            and self._voice_state == "idle"
            and voice_deps_available()
            and not self._pill_collapsed
        )

    def _update_voice_ui(self) -> None:
        recording = self._voice_state == "recording"
        transcribing = self._voice_state == "transcribing"
        self._mic_btn.setProperty("recording", "true" if recording else "false")
        self._mic_btn.setProperty("transcribing", "true" if transcribing else "false")
        self._mic_btn.style().unpolish(self._mic_btn)
        self._mic_btn.style().polish(self._mic_btn)
        if recording:
            self._voice_status.setText("recording…")
            self._voice_status.show()
            self._voice_level_meter.show()
            if not self._voice_pulse_timer.isActive():
                self._voice_pulse_timer.start(450)
        else:
            self._voice_pulse_timer.stop()
            self._voice_level_meter.hide()
            self._voice_level_meter.set_level(0.0)
            if transcribing:
                self._voice_status.setText("Transcribing…")
                self._voice_status.show()
            else:
                self._voice_status.hide()
        self._mic_btn.setEnabled(
            get_voice_enabled()
            and voice_deps_available()
            and not self._busy
            and self._voice_state != "transcribing"
        )

    def _tick_voice_pulse(self) -> None:
        self._voice_pulse_on = not self._voice_pulse_on
        self._mic_btn.setProperty("pulse", "true" if self._voice_pulse_on else "false")
        self._mic_btn.style().unpolish(self._mic_btn)
        self._mic_btn.style().polish(self._mic_btn)

    def _on_voice_level(self, level: float) -> None:
        self._voice_level_meter.set_level(level)

    def _on_mic_pressed(self) -> None:
        if get_voice_recording_mode() == "toggle":
            if self._voice_state == "recording":
                self._stop_voice_recording()
            elif self._voice_can_start():
                self._start_voice_recording(source="mic")
            return
        if self._voice_can_start():
            self._start_voice_recording(source="mic")

    def _on_mic_released(self) -> None:
        if get_voice_recording_mode() == "push_to_talk" and self._voice_state == "recording":
            self._stop_voice_recording()

    def _is_ptt_shortcut(self, event: QKeyEvent) -> bool:
        if self._voice_ptt_key_seq.isEmpty():
            return False
        pressed = QKeySequence(event.keyCombination())
        return pressed == self._voice_ptt_key_seq

    def _handle_voice_key_press(self, event: QKeyEvent) -> bool:
        if not get_voice_enabled() or event.isAutoRepeat() or not self._is_ptt_shortcut(event):
            return False
        mode = get_voice_recording_mode()
        if mode == "push_to_talk":
            if self._voice_can_start():
                self._start_voice_recording(source="keyboard")
            return True
        if self._voice_state == "recording":
            self._stop_voice_recording()
        elif self._voice_can_start():
            self._start_voice_recording(source="keyboard")
        return True

    def _handle_voice_key_release(self, event: QKeyEvent) -> bool:
        if not get_voice_enabled() or not self._is_ptt_shortcut(event):
            return False
        if (
            get_voice_recording_mode() == "push_to_talk"
            and self._voice_state == "recording"
            and self._voice_ptt_keyboard_held
        ):
            self._stop_voice_recording()
            return True
        return False

    def _start_voice_recording(self, *, source: str) -> None:
        if not self._voice_can_start():
            return
        if get_voice_transcription_mode(private_mode=self._private_mode) != "local":
            self._flash_status("Cloud transcription is not available yet.")
            return
        try:
            self._voice_recorder = AudioRecorder(
                on_level=lambda level: QTimer.singleShot(
                    0, lambda lvl=level: self._on_voice_level(lvl)
                ),
            )
            self._voice_recorder.start()
        except Exception as exc:
            log.warning("Failed to start voice recording", exc_info=True)
            self._flash_status(str(exc))
            self._voice_recorder = None
            return
        self._voice_state = "recording"
        self._voice_ptt_keyboard_held = source == "keyboard"
        _play_voice_beep()
        if get_voice_recording_mode() == "toggle":
            max_seconds = get_voice_toggle_max_seconds()
            self._voice_toggle_timer.start(max_seconds * 1000)
        self._update_voice_ui()

    def _stop_voice_recording(self, *, silent: bool = False) -> None:
        if self._voice_state != "recording":
            return
        self._voice_toggle_timer.stop()
        self._voice_ptt_keyboard_held = False
        audio = None
        if self._voice_recorder is not None:
            try:
                audio = self._voice_recorder.stop()
            except Exception:
                log.warning("Failed to stop voice recording", exc_info=True)
            self._voice_recorder = None
        if not silent:
            _play_voice_beep()
        if audio is None or getattr(audio, "size", 0) == 0:
            self._voice_state = "idle"
            self._update_voice_ui()
            if not silent:
                self._flash_status("No audio captured.")
            return
        self._voice_state = "transcribing"
        self._update_voice_ui()
        model_size = get_voice_model_size()
        self._voice_worker = TranscribeWorker(audio, model_size=model_size)
        self._voice_worker.finished.connect(self._on_transcribe_done)
        self._voice_worker.start()

    def _cancel_voice_transcription(self) -> None:
        if self._voice_worker is not None and self._voice_worker.isRunning():
            self._voice_worker.requestInterruption()
        self._voice_worker = None
        self._voice_state = "idle"
        self._update_voice_ui()

    def _on_voice_toggle_timeout(self) -> None:
        if self._voice_state == "recording":
            self._stop_voice_recording()
            self._flash_status("Recording stopped (max duration).")

    def _on_transcribe_done(self, payload: dict[str, Any]) -> None:
        self._voice_worker = None
        self._voice_state = "idle"
        self._update_voice_ui()
        if payload.get("ok"):
            text = str(payload.get("text") or "").strip()
            if text:
                self._insert_transcription(text)
                self._draft_save_timer.start(400)
            else:
                self._flash_status("No speech detected.")
        else:
            error = str(payload.get("error") or "Transcription failed.")
            self._flash_status(error)

    def _insert_transcription(self, text: str) -> None:
        current = self._input.effective_text()
        cursor = self._input.textCursor()
        if not current.strip():
            self._input.setPlainText(text)
            cursor = self._input.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self._input.setTextCursor(cursor)
        else:
            cursor.insertText(f" {text}")
        self._schedule_resize_input()
        self._input.setFocus()

    def _available_screen_rects(self) -> list[tuple[int, int, int, int]]:
        rects: list[tuple[int, int, int, int]] = []
        for screen in QApplication.screens():
            geo = screen.availableGeometry()
            rects.append((geo.x(), geo.y(), geo.width(), geo.height()))
        return rects

    def _primary_screen_rect(self) -> tuple[int, int, int, int] | None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return None
        geo = screen.availableGeometry()
        return geo.x(), geo.y(), geo.width(), geo.height()

    def _event_matches_sequence(self, event: QKeyEvent, seq: QKeySequence) -> bool:
        if seq.isEmpty():
            return False
        pressed = QKeySequence(event.keyCombination())
        return pressed == seq

    def _on_input_changed(self) -> None:
        self._schedule_resize_input()
        current = self._input.effective_text()
        self._char_count.update_count(len(current))
        self._sync_optimize_button()
        if self._last_optimized_input is not None and current != self._last_optimized_input:
            self._last_optimized_input = None
            self._session_has_optimization_result = False
        self._draft_save_timer.start(400)

    def _sync_optimize_button(self) -> None:
        self._optimize_btn.set_has_text(self._input.has_substantive_text())

    def _on_optimize_clicked(self) -> None:
        if not self._input.has_substantive_text():
            self._input.setFocus()
            return
        self._submit()

    def _maybe_show_first_run_example(self) -> None:
        if get_first_run_complete():
            return
        if self._input.has_substantive_text():
            return
        if load_draft():
            return
        self._input.show_ghost_example(PILL_FIRST_RUN_EXAMPLE)

    def _on_ghost_dismissed(self) -> None:
        set_first_run_complete(True)

    def _persist_draft(self) -> None:
        text = self._input.effective_text()
        if self._last_optimized_input is not None and text == self._last_optimized_input:
            return
        if text.strip():
            save_draft(text)
        else:
            clear_draft()

    def flush_draft(self) -> None:
        """Save draft immediately (hide, close, shutdown)."""
        self._draft_save_timer.stop()
        self._persist_draft()

    def _restore_draft_if_needed(self) -> None:
        if self._session_has_optimization_result:
            return
        if self._input.effective_text().strip():
            return
        saved = load_draft()
        if not saved:
            return
        self._input.blockSignals(True)
        self._input.setPlainText(saved)
        self._input.blockSignals(False)
        self._resize_input()

    def _show_pill_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(pill_menu_stylesheet())
        mode_action = menu.addAction(f"Mode: {self._mode_label().title()}")
        mode_action.setShortcut("Ctrl+M")
        mode_action.triggered.connect(self._toggle_mode)

        private_action = menu.addAction("Private session")
        private_action.setCheckable(True)
        private_action.setChecked(self._private_mode)
        if not self._private_key_seq.isEmpty():
            private_action.setShortcut(self._private_key_seq)
        private_action.triggered.connect(self._set_private_mode)

        menu.addSeparator()

        if self._pill_collapsed:
            expand_action = menu.addAction("Expand")
            expand_action.triggered.connect(self.expand)
        else:
            collapse_action = menu.addAction("Collapse")
            collapse_action.triggered.connect(self.collapse)

        menu.addSeparator()
        settings_action = menu.addAction("Settings…")
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._open_settings)

        menu.exec(self._pill.mapToGlobal(pos))

    def _open_settings(self) -> None:
        self._controller.show_settings()

    def _set_private_mode(self, checked: bool) -> None:
        self._private_mode = checked
        set_private_session(checked)
        if self._private_chip.isChecked() != checked:
            self._private_chip.set_checked_silent(checked)
        label = "Private session on" if checked else "Private session off"
        self._flash_status(label)

    def reload_private_session(self) -> None:
        """Sync private chip from config (after settings save)."""
        checked = get_private_session()
        self._private_mode = checked
        self._private_chip.set_checked_silent(checked)

    def _toggle_private_mode(self) -> None:
        self._set_private_mode(not self._private_mode)

    def _schedule_resize_input(self) -> None:
        """Defer autosize until QTextDocument layout has caught up."""
        QTimer.singleShot(0, self._resize_input)

    def _resize_input(self) -> None:
        if self._pill_collapsed:
            return
        self._input._emit_height()
        extra = 0
        if self._progress_bar.isVisible():
            extra += PROGRESS_HEIGHT + PILL_LAYOUT_SPACING
        row_widget = self._optimizing_row if self._optimizing_row.isVisible() else self._controls_row
        pill_h = (
            PILL_LAYOUT_MARGINS[1]
            + self._input.height()
            + PILL_LAYOUT_SPACING
            + extra
            + (PILL_LAYOUT_SPACING if self._progress_bar.isVisible() else 0)
            + row_widget.sizeHint().height()
            + PILL_LAYOUT_MARGINS[3]
        )
        pill_h = max(PILL_HEIGHT, pill_h)
        if self._pill.height() != pill_h:
            self._pill.setFixedHeight(pill_h)
        self._update_window_height()

    def _apply_chip_geometry(self) -> None:
        """Force square chip dimensions on the pill and top-level window."""
        self._pill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._pill.setMinimumSize(CHIP_SIZE, CHIP_SIZE)
        self._pill.setMaximumSize(CHIP_SIZE, CHIP_SIZE)
        self._pill.setFixedSize(CHIP_SIZE, CHIP_SIZE)
        self.setMinimumSize(CHIP_WINDOW_SIZE, CHIP_WINDOW_SIZE)
        self.setMaximumSize(CHIP_WINDOW_SIZE, CHIP_WINDOW_SIZE)
        self.setFixedSize(CHIP_WINDOW_SIZE, CHIP_WINDOW_SIZE)
        self.updateGeometry()

    def _release_chip_geometry(self) -> None:
        """Clear chip-only size constraints before restoring the expanded pill."""
        self._pill.setMinimumSize(0, 0)
        self._pill.setMaximumSize(_QT_WIDGETSIZE_MAX, _QT_WIDGETSIZE_MAX)
        self._pill.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.setMinimumWidth(WINDOW_MIN_WIDTH)
        self.setFixedWidth(WINDOW_WIDTH)
        self.setMaximumWidth(WINDOW_WIDTH)

    def _update_window_height(self) -> None:
        if self._pill_collapsed:
            self._apply_chip_geometry()
            return
        pill_h = self._pill.height()
        if self._result_expanded:
            result_h = self._result_frame.sizeHint().height()
            total_h = pill_h + result_h + ROOT_VERTICAL_MARGIN
        else:
            total_h = pill_h + ROOT_VERTICAL_MARGIN
        if self.height() != total_h:
            self.setFixedHeight(total_h)

    def _mode_label(self) -> str:
        mode = (load_config().get("mode") or "thorough").lower()
        return "fast" if mode == "fast" else "thorough"

    def _toggle_mode(self) -> None:
        if self._busy:
            return
        current = (load_config().get("mode") or "thorough").lower()
        new_mode = "fast" if current != "fast" else "thorough"
        try:
            set_mode(new_mode)
        except ValueError:
            return
        self._flash_status(f"Mode: {self._mode_label().title()}")
        self._update_mode_chip()

    def _update_mode_chip(self) -> None:
        self._mode_chip.set_label(self._mode_label().title())
        self._update_control_tooltips()

    def _show_mode_menu(self) -> None:
        if self._busy:
            return
        menu = QMenu(self)
        menu.setStyleSheet(pill_menu_stylesheet())
        current = self._mode_label().title()
        for label in ("Thorough", "Fast"):
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(label == current)

            def _make_handler(mode_label: str) -> Callable[[], None]:
                return lambda: self._select_mode(mode_label)

            action.triggered.connect(_make_handler(label))
        menu.exec(self._mode_chip.mapToGlobal(QPoint(0, self._mode_chip.height())))

    def _select_mode(self, mode_label: str) -> None:
        if self._busy:
            return
        try:
            set_mode(mode_label.lower())
        except ValueError:
            return
        self._flash_status(f"Mode: {self._mode_label().title()}")
        self._update_mode_chip()
        self._update_control_tooltips()

    def _shortcut_hint(self, seq: QKeySequence) -> str:
        if seq.isEmpty():
            return ""
        native = seq.toString(QKeySequence.SequenceFormat.NativeText)
        return f" ({native})" if native else ""

    def _update_control_tooltips(self) -> None:
        mode = self._mode_label().title()
        other = "Fast" if mode == "Thorough" else "Thorough"
        self._mode_chip.setToolTip(
            f"Mode: {mode} — click for {other} (Ctrl+M)"
        )
        private_hint = self._shortcut_hint(self._private_key_seq)
        self._private_chip.setToolTip(
            f"Private session — skip history{private_hint}"
        )

    def _refresh_project_selector(self) -> None:
        active = get_active_project()
        if active:
            name = str(active.get("name") or active.get("id") or "Project")
            self._project_chip.set_label(name)
            self._project_chip.set_project_name(name)
            tech = [str(t).strip() for t in (active.get("tech_stack") or []) if str(t).strip()]
            ptype = str(active.get("project_type") or "").strip()
            tooltip_parts = [f"Active project: {name}"]
            if ptype:
                tooltip_parts.append(f"Type: {ptype}")
            if tech:
                tooltip_parts.append(f"Tech stack: {', '.join(tech)}")
            self._project_chip.setToolTip("\n".join(tooltip_parts))
        else:
            self._project_chip.set_label("No project")
            self._project_chip.set_project_name(None)
            self._project_chip.setToolTip("Active project context")

    def _project_menu_stylesheet(self) -> str:
        return pill_menu_stylesheet()

    def _show_project_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(self._project_menu_stylesheet())
        active = get_active_project()
        active_id = str(active["id"]) if active else None

        no_project = menu.addAction("No project")
        no_project.setCheckable(True)
        no_project.setChecked(active_id is None)
        no_project.triggered.connect(lambda: self._select_project(None))

        projects = list_projects()
        if projects:
            menu.addSeparator()
            for project in projects:
                pid = str(project["id"])
                action = menu.addAction(str(project.get("name") or pid))

                def _make_handler(project_id: str) -> Callable[[], None]:
                    return lambda: self._select_project(project_id)

                action.triggered.connect(_make_handler(pid))
                action.setCheckable(True)
                action.setChecked(pid == active_id)

        menu.addSeparator()
        new_action = menu.addAction("+ New project…")
        new_action.triggered.connect(self._open_projects_settings_new)

        menu.exec(
            self._project_chip.mapToGlobal(
                QPoint(0, self._project_chip.height())
            )
        )

    def _select_project(self, project_id: str | None) -> None:
        try:
            set_active_project(project_id)
        except ValueError:
            return
        self._refresh_project_selector()
        if project_id:
            project = get_active_project()
            if project:
                self._flash_status(f"Project: {project.get('name')}")

    def _open_projects_settings_new(self) -> None:
        self._controller.show_settings(initial_tab="projects", new_project=True)

    def reload_project_selector(self) -> None:
        """Refresh project label after settings changes."""
        self._refresh_project_selector()

    def refresh_projects(self) -> None:
        """Alias for reload_project_selector (settings save callback)."""
        self.reload_project_selector()

    def _flash_status(self, message: str) -> None:
        QToolTip.showText(
            self._pill.mapToGlobal(QPoint(self._pill.width() // 2, self._pill.height())),
            message,
            self._pill,
            self._pill.rect(),
            1500,
        )

    def _submit(self) -> None:
        if self._busy:
            return
        text = self._input.effective_text().strip()
        if not text:
            return
        if not has_api_key():
            if not SetupDialog.run_if_needed(self):
                return

        if get_auto_inject_enabled():
            self._controller.refresh_inject_target()

        self._pending_optimize_text = text
        self._set_busy(True)
        skip_history = self._private_mode
        self._worker = OptimizeWorker(
            text,
            skip_history=skip_history,
            private_mode=self._private_mode,
        )
        self._worker.finished.connect(self._on_optimize_done)
        self._worker.progress.connect(self._on_optimize_progress)
        self._worker.start()

    def _show_optimizing_ui(self) -> None:
        model_id = get_active_model()
        self._pill_status.setProperty("danger", "false")
        self._pill_status.style().unpolish(self._pill_status)
        self._pill_status.style().polish(self._pill_status)
        self._pill_status.setText(f"Optimizing with {model_id}")
        self._settings_link_btn.hide()
        self._controls_row.hide()
        self._optimizing_row.show()
        self._progress_bar.start()
        self._resize_input()

    def _show_controls_ui(self) -> None:
        self._optimizing_row.hide()
        self._controls_row.show()
        self._pill_status.clear()
        self._settings_link_btn.hide()
        self._resize_input()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._input.setReadOnly(busy)
        if busy and self._voice_state == "recording":
            self._stop_voice_recording(silent=True)
        self._update_voice_ui()
        if busy:
            self._show_optimizing_ui()
        else:
            self._input.setReadOnly(False)
            if not self._optimizing_row.isVisible() or not self._pill_status.text():
                self._show_controls_ui()

    def _cancel_optimize(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
        self._worker = None
        self._busy = False
        self._input.setReadOnly(False)
        self._progress_bar.hide_bar()
        self._show_controls_ui()

    def _hide_progress_bar(self) -> None:
        self._progress_bar.hide_bar()
        self._show_controls_ui()

    def _format_optimize_error(self, error: str) -> tuple[str, bool]:
        lower = error.lower()
        if "cancelled" in lower:
            return "", False
        if "api key" in lower or "no api key" in lower:
            return "No API key set.", True
        if "rate limit" in lower or "busy" in lower or "429" in lower:
            return "Rate limited. Wait a moment and try again.", False
        if "authentication" in lower:
            return "Authentication failed. Check your API key in settings.", True
        return "Optimization failed. Try again.", False

    def _on_optimize_progress(self, message: str) -> None:
        if message:
            self._pill_status.setText(message)

    def _on_optimize_done(self, payload: dict[str, Any]) -> None:
        if payload.get("cancelled"):
            self._cancel_optimize()
            return

        self._worker = None
        self._busy = False
        self._input.setReadOnly(False)

        if payload.get("ok"):
            self._progress_bar.flash_success()
            self._progress_fade_timer.start(350)
            result = payload.get("result") or ""
            self._result_text.setPlainText(result)
            copied = payload.get("copied", False)
            if get_auto_copy_clipboard():
                self._status_label.setText(
                    "Copied to clipboard" if copied else "Done (clipboard copy failed)"
                )
            else:
                self._status_label.setText("Done")
            self._status_label.setStyleSheet(f"color: {C['success']}; font-size: 12px;")
            self._last_optimized_input = self._pending_optimize_text
            self._session_has_optimization_result = True
            clear_draft()
            self._update_inject_row()
            self._show_controls_ui()
        else:
            error = payload.get("error") or "Unknown error"
            message, opens_settings = self._format_optimize_error(str(error))
            self._progress_bar.flash_danger()
            QTimer.singleShot(200, lambda: self._progress_fade_timer.start(400))
            if message:
                self._pill_status.setProperty("danger", "true")
                self._pill_status.style().unpolish(self._pill_status)
                self._pill_status.style().polish(self._pill_status)
                self._pill_status.setText(message)
                self._settings_link_btn.setVisible(opens_settings)
                self._controls_row.hide()
                self._optimizing_row.show()
                QTimer.singleShot(2500, self._hide_progress_bar)
            else:
                self._hide_progress_bar()
            self._result_text.setPlainText(str(error))
            self._status_label.setText("Error")
            self._status_label.setStyleSheet(f"color: {C['danger']}; font-size: 12px;")
            self._hide_inject_row()

        if self._pill_collapsed:
            self.expand()
        if payload.get("ok"):
            self.expand_result()

    def _own_hwnd(self) -> int | None:
        try:
            wid = self.winId()
            return int(wid) if wid else None
        except Exception:
            return None

    def _update_inject_row(self) -> None:
        self._hide_inject_row()
        if not get_auto_inject_enabled():
            return
        target = self._controller.get_inject_target()
        if not can_inject_target(target, own_hwnd=self._own_hwnd()):
            return
        title = str((target or {}).get("title") or "Unknown window")
        self._inject_label.setText(f'Inject into: "{title}"')
        self._inject_row.show()
        self._update_window_height()

    def _hide_inject_row(self) -> None:
        if self._inject_row.isVisible():
            self._inject_row.hide()
            self._update_window_height()

    def _on_inject_clicked(self) -> None:
        target = self._controller.get_inject_target()
        if not target:
            self._flash_status("No inject target available. Use clipboard instead.")
            self._hide_inject_row()
            return

        hwnd = target.get("hwnd")
        title = target.get("title")
        process_name = target.get("process_name")
        if not is_target_valid(hwnd):
            self._flash_status("Target window is no longer available. Use clipboard instead.")
            self._hide_inject_row()
            self._controller.clear_inject_target()
            return
        if is_blocked_target(title, process_name):
            self._flash_status("Cannot inject into this target.")
            self._hide_inject_row()
            return

        text = self._result_text.toPlainText()
        self._inject_btn.setEnabled(False)

        def _do_inject() -> None:
            ok, message = inject_via_paste(int(hwnd), text)
            self._inject_btn.setEnabled(True)
            if ok:
                self._controller.clear_inject_target()
                self._hide_inject_row()
                self.collapse()
            else:
                self._flash_status(message)

        QTimer.singleShot(INJECT_DEFER_MS, _do_inject)

    def _copy_result(self) -> None:
        try:
            pyperclip.copy(self._result_text.toPlainText())
        except Exception:
            log.warning("Manual copy to clipboard failed", exc_info=True)

    def _resize_compact(self) -> None:
        self._result_expanded = False
        self._result_frame.hide()
        self._resize_input()

    def _resize_expanded(self) -> None:
        self._result_expanded = True
        self._result_frame.show()
        self._update_window_height()

    def collapse_result(self, reset_ui: bool = False) -> None:
        self._hide_inject_row()
        self._resize_compact()
        if reset_ui:
            self._reset_ui(clear_input=True)
        else:
            self._result_text.clear()
            self._status_label.clear()

    def expand_result(self) -> None:
        self._resize_expanded()

    def is_pill_collapsed(self) -> bool:
        return self._pill_collapsed

    def toggle_pill_collapse(self) -> None:
        if self._pill_collapsed:
            self.expand()
        else:
            self.collapse()

    def collapse(self) -> None:
        """Collapse the pill to a small floating chip (does not hide or clear draft)."""
        if self._pill_collapsed:
            return
        self.flush_draft()
        expanded_x, expanded_y = self.x(), self.y()
        self._expanded_geometry = (
            expanded_x,
            expanded_y,
            self.width(),
            self.height(),
        )
        if self._visible:
            set_window_position(expanded_x, expanded_y)
        self._pill_collapsed = True
        self._result_frame.hide()

        self._input.hide()
        self._progress_bar.hide()
        self._controls_row.hide()
        self._optimizing_row.hide()

        self._pill.setProperty("collapsed", "true")
        self._pill.style().unpolish(self._pill)
        self._pill.style().polish(self._pill)

        pill_layout = self._pill.layout()
        if pill_layout is not None:
            pill_layout.setContentsMargins(0, 0, 0, 0)
            pill_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._pill_icon.setFixedSize(SparkIcon.SIZE, SparkIcon.SIZE)
        self._apply_chip_geometry()
        x, y = self.x(), self.y()
        self._move_clamped(x, y)

        set_pill_collapsed(True)
        if self._visible:
            self._persist_window_position()

    def expand(self) -> None:
        """Expand from chip to full pill and focus the input."""
        if not self._pill_collapsed:
            return

        self._pill_collapsed = False

        self._pill.setProperty("collapsed", "false")
        self._pill.style().unpolish(self._pill)
        self._pill.style().polish(self._pill)

        pill_layout = self._pill.layout()
        if pill_layout is not None:
            pill_layout.setContentsMargins(*PILL_LAYOUT_MARGINS)
            pill_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._pill_icon.setFixedSize(SparkIcon.SIZE, SparkIcon.SIZE)
        self._input.show()
        self._controls_row.show()
        self._optimizing_row.hide()
        self._progress_bar.hide()

        self._release_chip_geometry()
        if self.width() < WINDOW_MIN_WIDTH:
            self.resize(WINDOW_WIDTH, self.height())
        self._resize_input()

        x, y = self.x(), self.y()
        self._move_clamped(x, y)
        set_window_position(self.x(), self.y())

        if self._result_expanded:
            self._result_frame.show()
            self._update_window_height()

        set_pill_collapsed(False)
        if self._visible:
            self._persist_window_position()
        self._restore_draft_if_needed()
        self._input.setFocus()

    def _screen_rect(self) -> tuple[int, int, int, int] | None:
        screens = self._available_screen_rects()
        if not screens:
            return None
        match = screen_for_window(
            self.x(),
            self.y(),
            self.width(),
            self.height(),
            screens,
        )
        if match is not None:
            return match
        return screens[0]

    def _clamp_position(self, x: int, y: int) -> tuple[int, int]:
        screens = self._available_screen_rects()
        if not screens:
            return x, y
        new_x, new_y, _ = validate_window_coords(
            x,
            y,
            self.width(),
            self.height(),
            screens,
        )
        return new_x, new_y

    def _move_clamped(self, x: int, y: int) -> None:
        clamped_x, clamped_y = self._clamp_position(x, y)
        self.move(clamped_x, clamped_y)

    def _apply_saved_position(self) -> None:
        saved_x, saved_y = get_window_position()
        if saved_x is not None and saved_y is not None:
            screens = self._available_screen_rects()
            if screens:
                new_x, new_y, rescued = validate_window_coords(
                    saved_x,
                    saved_y,
                    self.width(),
                    self.height(),
                    screens,
                )
                self.move(new_x, new_y)
                if rescued:
                    log.info(
                        "Rescued window from off-screen saved position to (%d, %d)",
                        new_x,
                        new_y,
                    )
                    self._persist_window_position(force=True)
            else:
                self._move_clamped(saved_x, saved_y)
        else:
            self._center_on_screen()
            self._persist_window_position(force=True)

    def validate_window_position(self) -> bool:
        """
        Re-clamp the current window position against available screens.
        Returns True when the position was corrected.
        """
        screens = self._available_screen_rects()
        if not screens:
            return False
        x, y = self.x(), self.y()
        new_x, new_y, rescued = validate_window_coords(
            x,
            y,
            self.width(),
            self.height(),
            screens,
        )
        if (new_x, new_y) == (x, y):
            return False
        self.move(new_x, new_y)
        if rescued:
            log.info("Window position validated and rescued to (%d, %d)", new_x, new_y)
        self._persist_window_position(force=True)
        return True

    def reset_window_position(self) -> None:
        """Center the popup or chip on the primary screen and persist."""
        primary = self._primary_screen_rect()
        if primary is None:
            return
        screen_x, screen_y, screen_w, screen_h = primary
        x, y = center_window_on_screen(
            self.width(),
            self.height(),
            screen_x,
            screen_y,
            screen_w,
            screen_h,
        )
        self.move(x, y)
        self._persist_window_position(force=True)
        log.info("Window position reset to primary screen center (%d, %d)", x, y)
        if self.isVisible():
            self.raise_()
            self.activateWindow()

    def _persist_window_position(self, *, force: bool = False) -> None:
        if not force and not self._visible:
            return
        pos = self.frameGeometry().topLeft()
        set_window_position(pos.x(), pos.y())

    def _schedule_persist_window_position(self) -> None:
        if not self._visible:
            return
        self._position_save_timer.start(250)

    def moveEvent(self, event) -> None:  # noqa: ANN001, N802
        super().moveEvent(event)
        if self._visible:
            self._schedule_persist_window_position()

    def _reset_ui(self, *, clear_input: bool = True) -> None:
        if clear_input:
            self._input.clear()
            self._last_optimized_input = None
            self._session_has_optimization_result = False
            clear_draft()
        self._result_text.clear()
        self._status_label.clear()
        self._private_mode = False
        set_private_session(False)
        self._private_chip.set_checked_silent(False)
        self._set_busy(False)
        self._sync_optimize_button()
        self._resize_input()

    def set_prompt_text(self, text: str) -> None:
        if self._pill_collapsed:
            self.expand()
        self._input.setPlainText(text)
        self._resize_input()
        self._input.setFocus()

    def set_prompt_and_output(self, input_text: str, output_text: str) -> None:
        if self._pill_collapsed:
            self.expand()
        self.set_prompt_text(input_text)
        self._result_text.setPlainText(output_text)
        self._status_label.setText("Loaded from history")
        self._status_label.setStyleSheet(f"color: {C['text_muted']}; font-size: 12px;")
        self.expand_result()

    def trigger_optimize(self, text: str | None = None) -> None:
        if text is not None:
            self.set_prompt_text(text)
        self._submit()

    def _center_on_screen(self) -> None:
        primary = self._primary_screen_rect()
        if primary is None:
            return
        screen_x, screen_y, screen_w, screen_h = primary
        x, y = center_window_on_screen(
            self.width(),
            self.height(),
            screen_x,
            screen_y,
            screen_w,
            screen_h,
        )
        self.move(x, y)

    def show_popup(
        self,
        *,
        force_expand: bool = False,
        force_collapse: bool = False,
        record_inject_target: bool = True,
    ) -> None:
        if record_inject_target:
            self._controller.record_inject_target_if_needed()

        if not has_api_key():
            SetupDialog.run_if_needed(self)

        self.collapse_result(reset_ui=False)
        self._restore_draft_if_needed()

        if force_collapse:
            target_collapsed = True
        elif force_expand:
            target_collapsed = False
        else:
            target_collapsed = get_pill_collapsed()

        if force_expand or not target_collapsed:
            if self._pill_collapsed:
                self.expand()
            else:
                self.setMinimumWidth(WINDOW_MIN_WIDTH)
                self.resize(WINDOW_WIDTH, self.height())
                self._resize_input()
        elif not self._pill_collapsed:
            self.collapse()
        else:
            self._apply_chip_geometry()

        self._apply_saved_position()
        self.validate_window_position()

        self.show()
        self.raise_()
        self.activateWindow()
        if not self._pill_collapsed:
            self._input.setFocus()
        self._visible = True

    def hide_popup(self) -> None:
        if self._voice_state == "recording":
            self._stop_voice_recording(silent=True)
        self.flush_draft()
        self._position_save_timer.stop()
        self._persist_window_position()
        if self._session_has_optimization_result:
            self.collapse_result(reset_ui=True)
        else:
            self.collapse_result(reset_ui=False)
        self.hide()
        self._visible = False

    def activate_for_user(self) -> None:
        """Show or bring forward the popup expanded and focus the input."""
        if self._visible and self.isVisible():
            self.validate_window_position()
            if self._pill_collapsed:
                self.expand()
            else:
                self.raise_()
                self.activateWindow()
                self._input.setFocus()
            return
        self.show_popup(force_expand=True)

    def activate_expanded(self) -> None:
        """Backward-compatible alias for global hotkey / tray open."""
        self.activate_for_user()

    def showEvent(self, event) -> None:  # noqa: ANN001, N802
        super().showEvent(event)
        self._schedule_resize_input()

    def toggle_popup(self, *, record_inject_target: bool = True) -> None:
        if self._visible and self.isVisible():
            self.hide_popup()
        else:
            self.show_popup(record_inject_target=record_inject_target)

    def toggle_collapse_global(self) -> None:
        """Global hotkey: hidden → chip; chip → expand; expanded → collapse."""
        action = collapse_global_action(
            is_visible=bool(self._visible and self.isVisible()),
            is_collapsed=self._pill_collapsed,
        )
        if action == "show_chip":
            self.show_popup(force_collapse=True)
        elif action == "expand":
            self.expand()
        else:
            self.collapse()

    def closeEvent(self, event) -> None:  # noqa: ANN001
        if self._voice_state == "recording":
            self._stop_voice_recording(silent=True)
        self.flush_draft()
        self._position_save_timer.stop()
        self._persist_window_position(force=True)
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Fallback when QShortcut does not fire (e.g. focus in nested widgets).
        if self._event_matches_sequence(event, self._hide_key_seq):
            self.hide_popup()
            event.accept()
            return
        if self._event_matches_sequence(event, self._collapse_key_seq):
            self.toggle_pill_collapse()
            event.accept()
            return
        if self._event_matches_sequence(event, self._private_key_seq):
            self._toggle_private_mode()
            event.accept()
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_M:
                self._toggle_mode()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Comma:
                self._open_settings()
                event.accept()
                return
        super().keyPressEvent(event)

    def changeEvent(self, event: QEvent) -> None:
        try:
            evt_type = event.type()
        except Exception:
            evt_type = None
            
        if evt_type == QEvent.Type.WindowDeactivate and self._visible and not self._busy:
            # Brief delay avoids hiding when opening setup or clicking child widgets
            QTimer.singleShot(80, self._maybe_hide_on_deactivate)
        super().changeEvent(event)

    def _maybe_hide_on_deactivate(self) -> None:
        if not self._visible or self._busy or self._pill_collapsed:
            return
        if not self.isActiveWindow():
            active = QApplication.activeWindow()
            if isinstance(active, SettingsDialog):
                return
            from history_ui import HistoryDialog

            if isinstance(active, HistoryDialog):
                return
            self.hide_popup()


class PopupController(QObject):
    """Owns the PyQt6 popup lifecycle; thread-safe entry points via signals."""

    _show_signal = pyqtSignal()
    _hide_signal = pyqtSignal()
    _toggle_signal = pyqtSignal()
    _toggle_collapse_global_signal = pyqtSignal()
    _show_expanded_signal = pyqtSignal()
    _history_signal = pyqtSignal()
    _settings_signal = pyqtSignal()
    _reset_position_signal = pyqtSignal()
    _validate_position_signal = pyqtSignal()
    _quit_signal = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.window: MetaPromptWindow | None = None
        self._lock = threading.Lock()
        self._visible = False
        self._on_quit: Callable[[], None] | None = None
        self._on_settings_saved: Callable[[], None] | None = None
        self._settings_tab: str | None = None
        self._settings_new_project = False
        self._inject_target: dict[str, Any] | None = None
        self._inject_target_from_hotkey = False

        self._show_signal.connect(self._show_main_thread)
        self._hide_signal.connect(self._hide_main_thread)
        self._toggle_signal.connect(self._toggle_main_thread)
        self._toggle_collapse_global_signal.connect(self._toggle_collapse_global_main_thread)
        self._show_expanded_signal.connect(self._show_expanded_main_thread)
        self._history_signal.connect(self._show_history_main_thread)
        self._settings_signal.connect(self._show_settings_main_thread)
        self._reset_position_signal.connect(self._reset_window_position_main_thread)
        self._validate_position_signal.connect(self._validate_window_position_main_thread)

    def set_quit_callback(self, cb: Callable[[], None]) -> None:
        self._on_quit = cb
        self._quit_signal.connect(cb)

    def set_settings_saved_callback(self, cb: Callable[[], None]) -> None:
        self._on_settings_saved = cb

    def request_quit(self) -> None:
        """Thread-safe quit entry (tray menu, hotkeys, etc.)."""
        log.info("Quit requested (marshaling to main thread)")
        self._quit_signal.emit()

    def create_window(self) -> MetaPromptWindow:
        self.window = MetaPromptWindow(self)
        return self.window

    def _exclude_hwnds(self) -> frozenset[int]:
        if self.window is None:
            return frozenset()
        try:
            wid = self.window.winId()
            return frozenset({int(wid)}) if wid else frozenset()
        except Exception:
            return frozenset()

    def record_inject_target_from_hotkey(self) -> None:
        """Capture foreground window on the hotkey thread before the pill is shown."""
        from inject import record_foreground_target

        target = record_foreground_target(exclude_hwnds=self._exclude_hwnds())
        self._inject_target = target or None
        self._inject_target_from_hotkey = bool(self._inject_target)

    def refresh_inject_target(self) -> None:
        """Re-capture the foreground window (e.g. immediately before optimize)."""
        from inject import record_foreground_target

        target = record_foreground_target(exclude_hwnds=self._exclude_hwnds())
        if target:
            self._inject_target = target
            self._inject_target_from_hotkey = False

    def record_inject_target_if_needed(self) -> None:
        """Capture foreground window when opening via tray/history (not hotkey)."""
        if self._inject_target_from_hotkey:
            self._inject_target_from_hotkey = False
            return
        from inject import record_foreground_target

        target = record_foreground_target(exclude_hwnds=self._exclude_hwnds())
        self._inject_target = target or None

    def get_inject_target(self) -> dict[str, Any] | None:
        return self._inject_target

    def clear_inject_target(self) -> None:
        self._inject_target = None
        self._inject_target_from_hotkey = False

    def show(self) -> None:
        self._show_signal.emit()

    def hide(self) -> None:
        self._hide_signal.emit()

    def toggle(self) -> None:
        """Thread-safe: toggle show/hide (expanded or chip)."""
        self._toggle_signal.emit()

    def toggle_from_hotkey(self) -> None:
        """Global hotkey: record foreground target before showing the pill."""
        if not self.is_visible:
            self.record_inject_target_from_hotkey()
        self.toggle()

    def toggle_collapse_global(self) -> None:
        """Thread-safe: global collapse/expand chip hotkey."""
        self._toggle_collapse_global_signal.emit()

    def toggle_collapse_global_from_hotkey(self) -> None:
        """Global collapse hotkey: record target only when showing from hidden."""
        with self._lock:
            if self.window is not None:
                action = collapse_global_action(
                    is_visible=bool(self.window._visible and self.window.isVisible()),
                    is_collapsed=self.window._pill_collapsed,
                )
                if action == "show_chip":
                    self.record_inject_target_from_hotkey()
        self.toggle_collapse_global()

    def _show_main_thread(self) -> None:
        with self._lock:
            if self.window is None:
                return
            self.window.show_popup(record_inject_target=not self._inject_target_from_hotkey)
            self._inject_target_from_hotkey = False
            self._visible = True

    def _hide_main_thread(self) -> None:
        with self._lock:
            if self.window is None:
                return
            self.window.hide_popup()
            self._visible = False

    def _toggle_main_thread(self) -> None:
        with self._lock:
            if self.window is None:
                return
            self.window.toggle_popup(record_inject_target=not self._inject_target_from_hotkey)
            self._inject_target_from_hotkey = False
            self._visible = self.window._visible

    def _toggle_collapse_global_main_thread(self) -> None:
        with self._lock:
            if self.window is None:
                return
            self.window.toggle_collapse_global()
            self._inject_target_from_hotkey = False
            self._visible = self.window._visible

    def _show_expanded_main_thread(self) -> None:
        with self._lock:
            if self.window is None:
                return
            if self.window._visible and self.window.isVisible():
                self.window.validate_window_position()
                if self.window._pill_collapsed:
                    self.window.expand()
                else:
                    self.window.raise_()
                    self.window.activateWindow()
                    self.window._input.setFocus()
                return
            self.window.show_popup(
                force_expand=True,
                record_inject_target=not self._inject_target_from_hotkey,
            )
            self._inject_target_from_hotkey = False
            self._visible = self.window._visible

    def collapse(self, reset_ui: bool = False) -> None:
        if self.window:
            if reset_ui:
                self.window.collapse_result(reset_ui=True)
            else:
                self.window.collapse()

    def expand(self) -> None:
        if self.window:
            self.window.expand()

    def expand_result(self) -> None:
        if self.window:
            self.window.expand_result()

    def show_expanded(self, *, capture_inject_target: bool = True) -> None:
        """Thread-safe: show popup expanded or expand from chip."""
        if capture_inject_target:
            self.record_inject_target_from_hotkey()
        self._show_expanded_signal.emit()

    def show_history(self) -> None:
        """Open the history browser dialog (thread-safe)."""
        self._history_signal.emit()

    def show_settings(
        self,
        *,
        initial_tab: str | None = None,
        new_project: bool = False,
    ) -> None:
        """Open the settings dialog (thread-safe)."""
        self._settings_tab = initial_tab
        self._settings_new_project = new_project
        self._settings_signal.emit()

    def validate_window_position(self) -> None:
        """Re-clamp popup position after monitor changes (thread-safe)."""
        self._validate_position_signal.emit()

    def reset_window_position(self) -> None:
        """Center popup on primary screen (thread-safe)."""
        self._reset_position_signal.emit()

    def _validate_window_position_main_thread(self) -> None:
        if self.window is not None:
            self.window.validate_window_position()

    def _reset_window_position_main_thread(self) -> None:
        if self.window is not None:
            self.window.reset_window_position()

    def _show_history_main_thread(self) -> None:
        if self.window is None:
            return
        from history_ui import HistoryDialog

        dlg = HistoryDialog(self.window)
        dlg.promptRestored.connect(self._on_history_use_prompt)
        dlg.use_both_requested.connect(self._on_history_use_both)
        dlg.rerun_requested.connect(self._on_history_rerun)
        dlg.exec()

    def _show_settings_main_thread(self) -> None:
        if self.window is None:
            return
        dlg = SettingsDialog(
            self.window,
            on_saved=self._notify_settings_saved,
            on_reset_window_position=self.reset_window_position,
            initial_tab=self._settings_tab,
            new_project=self._settings_new_project,
        )
        self._settings_tab = None
        self._settings_new_project = False
        dlg.exec()

    def _notify_settings_saved(self) -> None:
        self.reload_shortcuts()
        if self.window is not None:
            self.window.reload_project_selector()
            self.window.reload_private_session()
            self.window._reload_voice_settings()
        if self._on_settings_saved is not None:
            self._on_settings_saved()

    def reload_shortcuts(self) -> None:
        if self.window is not None:
            self.window.reload_shortcuts()

    def _on_history_use_prompt(self, text: str) -> None:
        if self.window is None:
            return
        self.show_expanded()
        self.window.set_prompt_text(text)

    def _on_history_use_both(self, input_text: str, output_text: str) -> None:
        if self.window is None:
            return
        self.show_expanded()
        self.window.set_prompt_and_output(input_text, output_text)

    def _on_history_rerun(self, text: str) -> None:
        if self.window is None:
            return
        self.show_expanded()
        self.window.trigger_optimize(text)

    def destroy(self) -> None:
        if self.window is None:
            return
        log.info("Destroying popup window")
        window = self.window
        self.window = None
        self._visible = False

        window.flush_draft()
        window._position_save_timer.stop()
        window._persist_window_position(force=True)
        window._progress_fade_timer.stop()
        worker = window._worker
        if worker is not None and worker.isRunning():
            log.info("Waiting for optimize worker to finish")
            worker.wait(1000)
            if worker.isRunning():
                log.warning("Optimize worker still running after timeout; terminating")
                worker.terminate()
                worker.wait(500)
        window._worker = None

        window.hide_popup()
        window.close()
        log.info("Popup window closed")

    @property
    def is_visible(self) -> bool:
        return self._visible


# Singleton used by main.py
controller = PopupController()
