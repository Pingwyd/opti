"""
PyQt6 settings window for Opti — sidebar-navigated, immediate-apply.

Every control writes to config.json as soon as it changes (debounced for
text inputs, immediate for toggles/combos/shortcuts). There is no Save/Cancel
step; the footer just says so. Persistence happens off the UI thread via
`DebouncedConfigWriter` so typing or toggling never blocks the window.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from PyQt6.QtCore import QObject, QPoint, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFontMetrics, QIcon, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from brand import APP_NAME, APP_VERSION, SETTINGS_TITLE, SETUP_TITLE
from config import (
    DEFAULT_HOTKEY,
    DEFAULT_HOTKEY_COLLAPSE,
    DEFAULT_SHORTCUT_COLLAPSE,
    DEFAULT_SHORTCUT_HIDE_TRAY,
    DEFAULT_SHORTCUT_PRIVATE,
    DEFAULT_VOICE_PTT_SHORTCUT,
    PROVIDER_PRESETS,
    VALID_PROVIDERS,
    get_provider,
    get_settings_window_geometry,
    global_hotkeys_conflict,
    has_api_key,
    hotkey_conflicts_with_shortcuts,
    in_app_shortcuts_conflict,
    is_recognized_model_id,
    load_config,
    normalize_hotkey_string,
    normalize_shortcut_string,
    save_config,
    set_api_key,
    set_settings_window_geometry,
    shortcuts_equal,
    update_config,
)
from history import DEFAULT_SENSITIVE_KEYWORDS, counts_by_project_name
from hotkey_service import parse_hotkey_to_pynput
from projects import create_project, delete_project, get_project, list_projects, update_project
from startup import (
    disable_start_with_windows,
    enable_start_with_windows,
    is_start_with_windows_enabled,
)
from ui_theme import (
    CORAL,
    FONT_BODY,
    FONT_CAPTION,
    FONT_MICRO,
    FONT_SECTION,
    FONT_SMALL,
    FONT_TITLE,
    TEXT_MUTED,
    WEIGHT_MEDIUM,
    WEIGHT_REGULAR,
    settings_font,
    settings_mono_font,
    settings_stylesheet,
)
from widgets import (
    Badge,
    KeyCapRow,
    SettingRow,
    Stepper,
    ToggleSwitch,
    format_relative_time,
    render_close_icon,
    render_nav_pixmap,
)

log = logging.getLogger(__name__)

# Pure-function API kept stable for tests (test_inject.py, test_voice.py) and
# any external callers — the monolithic "collect + validate + save" flow is no
# longer used by the dialog itself (which is immediate-apply per field), but
# remains a correct, testable round-trip of the config schema.
HISTORY_LIMIT_MIN = 50
HISTORY_LIMIT_MAX = 5000

# Range used by the Privacy pane's Stepper control specifically (tighter than
# the schema-level clamp above, which stays generous for direct API callers).
PRIVACY_HISTORY_MIN = 10
PRIVACY_HISTORY_MAX = 500
PRIVACY_HISTORY_STEP = 10

_write_lock = threading.Lock()


def build_settings_values(
    *,
    provider: str,
    api_key_input: str,
    hotkey: str,
    hotkey_collapse: str,
    model: str,
    model_fast: str,
    mode: str,
    persist_draft: bool,
    save_history: bool,
    exclude_sensitive: bool,
    exclude_sensitive_keywords: list[str] | None = None,
    history_limit: int,
    start_with_windows: bool,
    start_minimized_to_tray: bool = True,
    check_updates_on_launch: bool = False,
    shortcut_collapse: str,
    shortcut_hide_tray: str,
    shortcut_private: str,
    auto_copy_clipboard: bool,
    auto_inject_enabled: bool = False,
    include_project_context_in_private: bool = False,
    voice_enabled: bool = False,
    voice_transcription_mode: str = "local",
    voice_recording_mode: str = "push_to_talk",
    voice_model_size: str = "base",
    voice_toggle_max_seconds: int = 60,
    voice_ptt_shortcut: str = DEFAULT_VOICE_PTT_SHORTCUT,
) -> dict[str, Any]:
    """Build a config patch from form field values (testable without Qt)."""
    return {
        "provider": provider,
        "api_key_input": api_key_input.strip(),
        "hotkey": normalize_hotkey_string(hotkey, DEFAULT_HOTKEY),
        "hotkey_collapse": normalize_hotkey_string(hotkey_collapse, DEFAULT_HOTKEY_COLLAPSE),
        "model": model.strip(),
        "model_fast": model_fast.strip(),
        "mode": mode,
        "persist_draft": persist_draft,
        "save_history": save_history,
        "exclude_sensitive": exclude_sensitive,
        "exclude_sensitive_keywords": exclude_sensitive_keywords or [],
        "history_limit": max(HISTORY_LIMIT_MIN, min(HISTORY_LIMIT_MAX, history_limit)),
        "start_with_windows": start_with_windows,
        "start_minimized_to_tray": start_minimized_to_tray,
        "check_updates_on_launch": check_updates_on_launch,
        "shortcut_collapse": normalize_shortcut_string(
            shortcut_collapse, DEFAULT_SHORTCUT_COLLAPSE
        ),
        "shortcut_hide_tray": normalize_shortcut_string(
            shortcut_hide_tray, DEFAULT_SHORTCUT_HIDE_TRAY
        ),
        "shortcut_private": normalize_shortcut_string(shortcut_private, DEFAULT_SHORTCUT_PRIVATE),
        "auto_copy_clipboard": auto_copy_clipboard,
        "auto_inject_enabled": auto_inject_enabled,
        "include_project_context_in_private": include_project_context_in_private,
        "voice_enabled": voice_enabled,
        "voice_transcription_mode": (
            "local" if str(voice_transcription_mode).lower() != "cloud" else "cloud"
        ),
        "voice_recording_mode": (
            "toggle" if str(voice_recording_mode).lower() == "toggle" else "push_to_talk"
        ),
        "voice_model_size": str(voice_model_size or "base").lower().strip(),
        "voice_toggle_max_seconds": max(5, min(600, int(voice_toggle_max_seconds))),
        "voice_ptt_shortcut": normalize_shortcut_string(
            voice_ptt_shortcut, DEFAULT_VOICE_PTT_SHORTCUT
        ),
    }


def apply_settings_values(values: dict[str, Any], *, require_api_key: bool = False) -> str | None:
    """
    Persist settings to config.json and sync Windows startup.

    Returns an error message on validation failure, else None. Pure/testable;
    not called by the dialog itself, which writes fields individually.
    """
    api_key_input = str(values.get("api_key_input") or "")
    if require_api_key and not api_key_input and not has_api_key():
        return "API key cannot be empty."

    provider = str(values.get("provider") or "gemini").lower().strip()
    if provider not in VALID_PROVIDERS:
        return f"Unknown provider: {provider}"

    shortcut_collapse = normalize_shortcut_string(
        str(values.get("shortcut_collapse") or ""), DEFAULT_SHORTCUT_COLLAPSE
    )
    shortcut_hide_tray = normalize_shortcut_string(
        str(values.get("shortcut_hide_tray") or ""), DEFAULT_SHORTCUT_HIDE_TRAY
    )
    shortcut_private = normalize_shortcut_string(
        str(values.get("shortcut_private") or ""), DEFAULT_SHORTCUT_PRIVATE
    )
    hotkey = normalize_hotkey_string(str(values.get("hotkey") or ""), DEFAULT_HOTKEY)
    hotkey_collapse = normalize_hotkey_string(
        str(values.get("hotkey_collapse") or ""), DEFAULT_HOTKEY_COLLAPSE
    )

    if in_app_shortcuts_conflict(shortcut_collapse, shortcut_hide_tray, shortcut_private):
        return "In-app shortcuts must each be unique."
    if global_hotkeys_conflict(hotkey, hotkey_collapse):
        return "Global hotkeys must each be unique."
    if hotkey_conflicts_with_shortcuts(
        hotkey,
        shortcut_collapse,
        shortcut_hide_tray,
        shortcut_private,
        hotkey_collapse=hotkey_collapse,
    ):
        return "Global hotkeys cannot match an in-app shortcut."

    cfg = load_config()
    cfg["provider"] = provider
    cfg["hotkey"] = hotkey
    cfg["hotkey_collapse"] = hotkey_collapse
    cfg["model"] = str(values.get("model") or PROVIDER_PRESETS[provider]["model"])
    cfg["model_fast"] = str(values.get("model_fast") or PROVIDER_PRESETS[provider]["model_fast"])
    cfg["mode"] = str(values.get("mode") or "thorough")
    cfg["persist_draft"] = bool(values.get("persist_draft", True))
    cfg["save_history"] = bool(values.get("save_history", True))
    cfg["exclude_sensitive"] = bool(values.get("exclude_sensitive", False))
    cfg["exclude_sensitive_keywords"] = values.get("exclude_sensitive_keywords", [])
    cfg["history_limit"] = int(values.get("history_limit") or 50)
    cfg["start_with_windows"] = bool(values.get("start_with_windows", False))
    cfg["start_minimized_to_tray"] = bool(values.get("start_minimized_to_tray", True))
    cfg["check_updates_on_launch"] = bool(values.get("check_updates_on_launch", False))
    cfg["shortcut_collapse"] = shortcut_collapse
    cfg["shortcut_hide_tray"] = shortcut_hide_tray
    cfg["shortcut_private"] = shortcut_private
    cfg["auto_copy_clipboard"] = bool(values.get("auto_copy_clipboard", True))
    cfg["auto_inject_enabled"] = bool(values.get("auto_inject_enabled", False))
    cfg["include_project_context_in_private"] = bool(
        values.get("include_project_context_in_private", False)
    )
    cfg["voice_enabled"] = bool(values.get("voice_enabled", False))
    cfg["voice_transcription_mode"] = str(values.get("voice_transcription_mode") or "local")
    cfg["voice_recording_mode"] = str(values.get("voice_recording_mode") or "push_to_talk")
    cfg["voice_model_size"] = str(values.get("voice_model_size") or "base")
    cfg["voice_toggle_max_seconds"] = int(values.get("voice_toggle_max_seconds") or 60)
    cfg["voice_ptt_shortcut"] = normalize_shortcut_string(
        str(values.get("voice_ptt_shortcut") or ""), DEFAULT_VOICE_PTT_SHORTCUT
    )
    save_config(cfg)

    if api_key_input:
        set_api_key(api_key_input)

    want_startup = bool(values.get("start_with_windows", False))
    have_startup = is_start_with_windows_enabled()
    if want_startup and not have_startup:
        enable_start_with_windows()
    elif not want_startup and have_startup:
        disable_start_with_windows()

    return None


def compute_shortcut_conflicts(
    hotkey: str,
    hotkey_collapse: str,
    shortcut_collapse: str,
    shortcut_hide: str,
    shortcut_private: str,
) -> dict[str, bool]:
    """
    Pure pairwise duplicate-detection across the five configurable bindings.

    Used by the Shortcuts pane to flag conflicts live as the user records new
    combos; kept standalone so it's testable without instantiating any Qt
    widgets.
    """
    pairs = {
        "hotkey": hotkey,
        "hotkey_collapse": hotkey_collapse,
        "shortcut_collapse": shortcut_collapse,
        "shortcut_hide_tray": shortcut_hide,
        "shortcut_private": shortcut_private,
    }
    conflicts = dict.fromkeys(pairs, False)
    items = list(pairs.items())
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            k1, v1 = items[i]
            k2, v2 = items[j]
            if shortcuts_equal(v1, v2):
                conflicts[k1] = True
                conflicts[k2] = True
    return conflicts


# ---------------------------------------------------------------------------
# Background persistence — off the UI thread, transient daemon threads.
#
# (Deliberately not QRunnable/QThreadPool: a QObject+QRunnable subclass hits
# a PyQt6 multiple-inheritance wrapper bug that crashes the interpreter once
# QThreadPool auto-deletes the job. A plain daemon `threading.Thread` that
# emits a signal owned by a main-thread QObject is fully supported — Qt only
# cares about the *receiver's* thread affinity when deciding to queue.)
# ---------------------------------------------------------------------------


class DebouncedConfigWriter(QObject):
    """
    Coalesces rapid config writes into a single debounced disk write.

    - `write(patch, immediate=True)` for toggles/combos: no artificial delay.
    - `write(patch, immediate=False)` for text inputs: restarts a 400ms timer;
      rapid keystrokes collapse into one merged write.
    - `run_task(fn)` for arbitrary background work (project CRUD) serialized
      with config writes via the same lock.
    """

    saved = pyqtSignal(dict)
    task_done = pyqtSignal(object)

    def __init__(self, delay_ms: int = 400, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._delay_ms = delay_ms
        self._pending: dict[str, Any] = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._flush)

    def write(self, patch: dict[str, Any], *, immediate: bool = True) -> None:
        self._pending.update(patch)
        if immediate:
            self._timer.stop()
            self._flush()
        else:
            self._timer.start(self._delay_ms)

    def run_task(self, fn: Callable[[], Any]) -> None:
        def _worker() -> None:
            try:
                with _write_lock:
                    result = fn()
            except Exception:
                log.exception("Opti settings: background task failed")
                return
            try:
                self.task_done.emit(result)
            except RuntimeError:
                pass  # dialog already closed/destroyed; write already committed

        threading.Thread(target=_worker, daemon=True).start()

    def pending_patch(self) -> dict[str, Any]:
        return dict(self._pending)

    def _flush(self) -> None:
        if not self._pending:
            return
        patch = self._pending
        self._pending = {}

        def _worker(p: dict[str, Any] = patch) -> None:
            try:
                with _write_lock:
                    update_config(p)
            except Exception:
                log.exception("Opti settings: background write failed")
                return
            try:
                self.saved.emit(p)
            except RuntimeError:
                pass  # dialog already closed/destroyed; write already committed

        threading.Thread(target=_worker, daemon=True).start()

    def shutdown(self) -> None:
        """Flush any pending debounced write immediately (fire-and-forget)."""
        if self._timer.isActive():
            self._timer.stop()
            self._flush()


# ---------------------------------------------------------------------------
# Small dialog-scoped widgets
# ---------------------------------------------------------------------------


class _TitleBar(QWidget):
    """Frameless drag handle + close button, matching the main pill's chrome."""

    close_requested = pyqtSignal()

    def __init__(self, dialog: QDialog, *, title: str) -> None:
        super().__init__(dialog)
        self.setObjectName("settingsTitleBar")
        self._dialog = dialog
        self._drag_offset: QPoint | None = None
        self.setFixedHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 12, 0)
        layout.setSpacing(9)

        dot = QLabel(self)
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background: {CORAL}; border-radius: 4px;")
        layout.addWidget(dot)

        self._label = QLabel(title, self)
        self._label.setObjectName("settingsWindowTitle")
        self._label.setFont(settings_font(FONT_SMALL, WEIGHT_MEDIUM))
        layout.addWidget(self._label)
        layout.addStretch(1)

        close_btn = QPushButton(self)
        close_btn.setObjectName("settingsCloseBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setIcon(QIcon(render_close_icon(TEXT_MUTED)))
        close_btn.setIconSize(QSize(12, 12))
        close_btn.clicked.connect(self.close_requested.emit)
        layout.addWidget(close_btn)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self._dialog.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._dialog.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class _ApiKeyControl(QWidget):
    """
    API key row control: a status indicator, not a persistent input.

    Set   -> "\u2713 Set    Replace"
    Unset -> "Not set    Add key"
    Editing -> masked input + confirm/cancel
    """

    key_committed = pyqtSignal(str)  # new plaintext key, or "" to clear

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._check = QLabel("\u2713", self)
        self._check.setObjectName("successCheck")
        self._check.setFont(settings_font(FONT_CAPTION, WEIGHT_MEDIUM))
        layout.addWidget(self._check)

        self._status_label = QLabel("Not set", self)
        self._status_label.setFont(settings_font(FONT_CAPTION))
        layout.addWidget(self._status_label)

        self._action_btn = QPushButton("Add key", self)
        self._action_btn.setObjectName("linkAction")
        self._action_btn.setFont(settings_font(FONT_CAPTION, WEIGHT_MEDIUM))
        self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action_btn.setFlat(True)
        self._action_btn.clicked.connect(self.start_editing)
        layout.addWidget(self._action_btn)

        self._edit_input = QLineEdit(self)
        self._edit_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._edit_input.setPlaceholderText("Paste API key")
        self._edit_input.setFont(settings_mono_font(FONT_CAPTION))
        self._edit_input.returnPressed.connect(self._confirm_edit)
        self._edit_input.hide()
        layout.addWidget(self._edit_input, 1)

        self._confirm_btn = QPushButton("\u2713", self)
        self._confirm_btn.setObjectName("linkAction")
        self._confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._confirm_btn.setFlat(True)
        self._confirm_btn.hide()
        self._confirm_btn.clicked.connect(self._confirm_edit)
        layout.addWidget(self._confirm_btn)

        self._cancel_btn = QPushButton("\u2715", self)
        self._cancel_btn.setObjectName("linkAction")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setFlat(True)
        self._cancel_btn.hide()
        self._cancel_btn.clicked.connect(self._cancel_edit)
        layout.addWidget(self._cancel_btn)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocusProxy(self._action_btn)

    def refresh(self, *, has_key: bool) -> None:
        self._edit_input.hide()
        self._edit_input.clear()
        self._confirm_btn.hide()
        self._cancel_btn.hide()
        self._check.setVisible(has_key)
        self._status_label.setText("Set" if has_key else "Not set")
        self._status_label.setStyleSheet("" if has_key else f"color: {TEXT_MUTED};")
        self._action_btn.setText("Replace" if has_key else "Add key")
        self._status_label.show()
        self._action_btn.show()

    def start_editing(self) -> None:
        self._status_label.hide()
        self._check.hide()
        self._action_btn.hide()
        self._edit_input.show()
        self._edit_input.setFocus()
        self._confirm_btn.show()
        self._cancel_btn.show()

    def _confirm_edit(self) -> None:
        value = self._edit_input.text().strip()
        self.key_committed.emit(value)

    def _cancel_edit(self) -> None:
        self.refresh(has_key=has_api_key())


class _PatternsDialog(QDialog):
    """Small modal listing/editing the sensitive-pattern exclusion list."""

    def __init__(self, patterns: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("patternsDialog")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(380, 320)
        self.setStyleSheet(settings_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("Sensitive patterns", self)
        title.setFont(settings_font(FONT_SECTION, WEIGHT_MEDIUM))
        layout.addWidget(title)

        subtitle = QLabel(
            "One pattern per line. Prompts matching any pattern are skipped from history.",
            self,
        )
        subtitle.setFont(settings_font(FONT_CAPTION))
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {TEXT_MUTED};")
        layout.addWidget(subtitle)

        self._edit = QTextEdit(self)
        self._edit.setPlainText("\n".join(patterns))
        self._edit.setFont(settings_mono_font(FONT_CAPTION))
        layout.addWidget(self._edit, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        done_btn = QPushButton("Done", self)
        done_btn.setObjectName("footerCloseBtn")
        done_btn.setFont(settings_font(FONT_SMALL, WEIGHT_MEDIUM))
        done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        done_btn.clicked.connect(self.accept)
        btn_row.addWidget(done_btn)
        layout.addLayout(btn_row)

    def patterns(self) -> list[str]:
        return [line.strip() for line in self._edit.toPlainText().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Projects sidebar row — owns highlight chrome (QListWidget::item QSS does not
# align with setItemWidget rows once content height grows beyond one line).
# ---------------------------------------------------------------------------


class _ProjectListItem(QWidget):
    def __init__(self, name: str, count: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("projectListItem")
        self.setProperty("selected", "false")
        self.setProperty("hovered", "false")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        badge = Badge(name, self)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignLeft)

        count_label = QLabel(f"{count} prompt{'s' if count != 1 else ''}", self)
        count_label.setObjectName("projectCount")
        count_label.setFont(settings_font(FONT_MICRO))
        layout.addWidget(count_label)

        fm_count = QFontMetrics(count_label.font())
        content_h = badge.sizeHint().height() + layout.spacing() + fm_count.height()
        self.setFixedHeight(content_h + 16)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        if selected:
            self.setProperty("hovered", "false")
        self._repolish()

    def enterEvent(self, event) -> None:  # noqa: N802
        if self.property("selected") != "true":
            self.setProperty("hovered", "true")
            self._repolish()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.setProperty("hovered", "false")
        self._repolish()
        super().leaveEvent(event)

    def _repolish(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)

    def sizeHint(self) -> QSize:
        return QSize(160, self.height())


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------


class SettingsDialog(QDialog):
    """Sidebar-navigated, immediate-apply settings window."""

    PANE_DEFS: list[tuple[str, str, str]] = [
        ("connection", "Connection", "connection"),
        ("privacy", "Privacy", "privacy"),
        ("shortcuts", "Shortcuts", "shortcuts"),
        ("startup", "Startup", "startup"),
        ("projects", "Projects", "projects"),
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        first_run: bool = False,
        focus_api_key: bool = False,
        on_saved: Callable[[], None] | None = None,
        on_reset_window_position: Callable[[], None] | None = None,
        initial_tab: str | None = None,
        new_project: bool = False,
    ) -> None:
        super().__init__(parent)
        self._first_run = first_run
        self._focus_api_key = focus_api_key or first_run
        self._on_saved = on_saved
        self._on_reset_window_position = on_reset_window_position
        self._initial_tab = initial_tab
        self._new_project = new_project

        self._selected_project_id: str | None = None
        self._loading_project_detail = False
        self._pending_project_fields: dict[str, str] = {}
        self._pending_new_project = False
        self._pending_delete_project = False
        self._last_good_shortcuts: dict[str, str] = {}
        self._shortcut_caps: dict[str, KeyCapRow] = {}
        self._shortcut_rows: dict[str, SettingRow] = {}

        self.setObjectName("settingsDialog")
        self.setWindowTitle(SETUP_TITLE if first_run else SETTINGS_TITLE)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumSize(880, 560)

        self._writer = DebouncedConfigWriter(400, self)
        self._writer.saved.connect(self._on_config_saved)
        self._writer.task_done.connect(self._on_project_task_done)

        self._geometry_timer = QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.timeout.connect(self._persist_geometry)

        self._project_save_timer = QTimer(self)
        self._project_save_timer.setSingleShot(True)
        self._project_save_timer.timeout.connect(self._flush_project_save)

        self._build_ui()
        self.setStyleSheet(settings_stylesheet())
        self._load_all()
        self._wire_tab_order()

        if self._first_run:
            self.resize(880, 560)
            self._center_on_primary_screen()
        else:
            self._restore_geometry()

        if self._initial_tab:
            self._select_pane(self._initial_tab)
        if self._new_project:
            self._select_pane("projects")
            self._on_new_project()
        if self._focus_api_key:
            self._select_pane("connection")
            QTimer.singleShot(0, self._api_key_control.start_editing)

    # -- window chrome -----------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: ANN001
        self._writer.shutdown()
        if self._project_save_timer.isActive():
            self._project_save_timer.stop()
            self._flush_project_save()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        if not self._first_run:
            self._geometry_timer.start(400)

    def moveEvent(self, event) -> None:  # noqa: ANN001
        super().moveEvent(event)
        if not self._first_run:
            self._geometry_timer.start(400)

    def _persist_geometry(self) -> None:
        set_settings_window_geometry(self.x(), self.y(), self.width(), self.height())

    def _restore_geometry(self) -> None:
        x, y, w, h = get_settings_window_geometry()
        self.resize(w, h)
        if x is not None and y is not None:
            self.move(x, y)
        else:
            self._center_on_primary_screen()

    def _center_on_primary_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

    # -- generic write helpers ----------------------------------------------

    def _write(self, patch: dict[str, Any], *, immediate: bool = True) -> None:
        self._writer.write(patch, immediate=immediate)

    def _on_config_saved(self, _patch: dict[str, Any]) -> None:
        if self._on_saved is not None:
            self._on_saved()

    # -- layout scaffolding ---------------------------------------------------

    def _build_pane(self, title: str, subtitle: str) -> tuple[QScrollArea, QVBoxLayout]:
        content = QWidget()
        content.setObjectName("settingsPane")
        outer = QVBoxLayout(content)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(4)

        title_label = QLabel(title, content)
        title_label.setObjectName("paneTitle")
        title_label.setFont(settings_font(FONT_TITLE, WEIGHT_MEDIUM))
        outer.addWidget(title_label)

        subtitle_label = QLabel(subtitle, content)
        subtitle_label.setObjectName("paneSubtitle")
        subtitle_label.setFont(settings_font(FONT_BODY))
        subtitle_label.setWordWrap(True)
        outer.addWidget(subtitle_label)
        outer.addSpacing(14)

        scroll = QScrollArea()
        scroll.setObjectName("settingsPaneScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        scroll.setViewportMargins(0, 0, 6, 0)
        return scroll, outer

    @staticmethod
    def _new_group(outer: QVBoxLayout) -> QVBoxLayout:
        group = QVBoxLayout()
        group.setContentsMargins(0, 0, 0, 0)
        group.setSpacing(0)
        outer.addLayout(group)
        return group

    @staticmethod
    def _finalize_rows(group: QVBoxLayout) -> None:
        last_row: SettingRow | None = None
        for i in range(group.count()):
            widget = group.itemAt(i).widget()
            if isinstance(widget, SettingRow):
                last_row = widget
        if last_row is not None:
            last_row.set_last(True)

    @staticmethod
    def _add_eyebrow(outer: QVBoxLayout, text: str) -> None:
        label = QLabel(text.upper())
        label.setObjectName("groupEyebrow")
        label.setFont(settings_font(FONT_MICRO, WEIGHT_MEDIUM))
        outer.addSpacing(6)
        outer.addWidget(label)
        outer.addSpacing(2)

    def _select_pane(self, pane_id: str) -> None:
        for row, (pid, _, _) in enumerate(self.PANE_DEFS):
            if pid == pane_id:
                self._nav.setCurrentRow(row)
                return

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        shell = QFrame(self)
        shell.setObjectName("settingsShell")
        root.addWidget(shell)

        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        title_text = "Connect your API key" if self._first_run else "Settings"
        title_bar = _TitleBar(self, title=title_text)
        title_bar.close_requested.connect(self.close)
        shell_layout.addWidget(title_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._nav = QListWidget(shell)
        self._nav.setObjectName("settingsNav")
        self._nav.setFixedWidth(160)
        self._nav.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._nav.currentRowChanged.connect(self._on_nav_changed)
        body.addWidget(self._nav)

        self._stack = QStackedWidget(shell)
        body.addWidget(self._stack, 1)

        shell_layout.addLayout(body, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(22, 12, 16, 14)
        footer.setSpacing(8)
        hint = QLabel("Changes apply immediately", shell)
        hint.setObjectName("footerHint")
        hint.setFont(settings_font(FONT_CAPTION))
        footer.addWidget(hint)
        footer.addStretch(1)
        close_btn = QPushButton("Close", shell)
        close_btn.setObjectName("footerCloseBtn")
        close_btn.setFont(settings_font(FONT_SMALL, WEIGHT_MEDIUM))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        footer.addWidget(close_btn)
        footer.addWidget(QSizeGrip(shell))
        shell_layout.addLayout(footer)

        panes = [
            self._build_connection_pane(),
            self._build_privacy_pane(),
            self._build_shortcuts_pane(),
            self._build_startup_pane(),
            self._build_projects_pane(),
        ]
        for (_pane_id, label, icon_kind), pane_widget in zip(self.PANE_DEFS, panes):
            item = QListWidgetItem(render_nav_pixmap(icon_kind), label)
            item.setFont(settings_font(FONT_SMALL))
            item.setSizeHint(QSize(140, 36))
            self._nav.addItem(item)
            self._stack.addWidget(pane_widget)

        if self._first_run:
            self._nav.hide()

        self._nav.setCurrentRow(0)

    # -- Connection pane ------------------------------------------------------

    def _model_field_control(self, line_edit: QLineEdit, on_reset: Callable[[], None]) -> QWidget:
        box = QWidget()
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        line_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(line_edit)
        reset_btn = QPushButton("Reset to default", box)
        reset_btn.setObjectName("linkAction")
        reset_btn.setFont(settings_font(FONT_MICRO))
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setFlat(True)
        reset_btn.clicked.connect(on_reset)
        layout.addWidget(reset_btn, 0, Qt.AlignmentFlag.AlignRight)
        return box

    def _build_connection_pane(self) -> QScrollArea:
        scroll, outer = self._build_pane("Connection", "Provider, credentials, and model IDs")
        group = self._new_group(outer)

        self._provider_row = SettingRow("Provider")
        self._provider_combo = QComboBox()
        self._provider_combo.setFont(settings_font(FONT_BODY))
        for provider_id in VALID_PROVIDERS:
            self._provider_combo.addItem(PROVIDER_PRESETS[provider_id]["label"], provider_id)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self._provider_row.set_control(self._provider_combo)
        group.addWidget(self._provider_row)

        self._api_key_row = SettingRow("API key", "Stored via DPAPI")
        self._api_key_control = _ApiKeyControl()
        self._api_key_control.key_committed.connect(self._on_api_key_committed)
        self._api_key_row.set_control(self._api_key_control)
        group.addWidget(self._api_key_row)

        self._model_row = SettingRow("Thorough model")
        self._model_input = QLineEdit()
        self._model_input.setFont(settings_mono_font(FONT_CAPTION))
        self._model_input.textChanged.connect(
            lambda text: self._write({"model": text.strip()}, immediate=False)
        )
        self._model_input.editingFinished.connect(
            lambda: self._validate_model_field(self._model_row, self._model_input)
        )
        self._model_row.set_control(
            self._model_field_control(self._model_input, lambda: self._reset_model_field("model")),
            stretch=True,
        )
        group.addWidget(self._model_row)

        self._model_fast_row = SettingRow("Fast model")
        self._model_fast_input = QLineEdit()
        self._model_fast_input.setFont(settings_mono_font(FONT_CAPTION))
        self._model_fast_input.textChanged.connect(
            lambda text: self._write({"model_fast": text.strip()}, immediate=False)
        )
        self._model_fast_input.editingFinished.connect(
            lambda: self._validate_model_field(self._model_fast_row, self._model_fast_input)
        )
        self._model_fast_row.set_control(
            self._model_field_control(
                self._model_fast_input, lambda: self._reset_model_field("model_fast")
            ),
            stretch=True,
        )
        group.addWidget(self._model_fast_row)

        self._persist_draft_row = SettingRow(
            "Remember draft text", "Persist input between sessions"
        )
        self._persist_draft_toggle = ToggleSwitch()
        self._persist_draft_toggle.toggled.connect(lambda v: self._write({"persist_draft": v}))
        self._persist_draft_row.set_control(self._persist_draft_toggle)
        group.addWidget(self._persist_draft_row)

        self._finalize_rows(group)
        outer.addStretch(1)
        return scroll

    def _validate_model_field(self, row: SettingRow, edit: QLineEdit) -> None:
        provider = str(self._provider_combo.currentData() or "gemini")
        text = edit.text().strip()
        if text and not is_recognized_model_id(provider, text):
            row.set_helper_text("Unrecognized model ID. Optimization may fail.", danger=True)
        else:
            row.set_helper_text("")

    def _on_provider_changed(self, _index: int) -> None:
        provider = str(self._provider_combo.currentData() or "gemini")
        preset = PROVIDER_PRESETS[provider]

        self._model_input.blockSignals(True)
        self._model_input.setText(str(preset["model"]))
        self._model_input.blockSignals(False)

        self._model_fast_input.blockSignals(True)
        self._model_fast_input.setText(str(preset["model_fast"]))
        self._model_fast_input.blockSignals(False)

        self._validate_model_field(self._model_row, self._model_input)
        self._validate_model_field(self._model_fast_row, self._model_fast_input)
        self._write(
            {"provider": provider, "model": preset["model"], "model_fast": preset["model_fast"]}
        )

    def _reset_model_field(self, field: str) -> None:
        provider = str(self._provider_combo.currentData() or "gemini")
        preset = PROVIDER_PRESETS[provider]
        value = str(preset[field])
        if field == "model":
            self._model_input.setText(value)
            self._validate_model_field(self._model_row, self._model_input)
        else:
            self._model_fast_input.setText(value)
            self._validate_model_field(self._model_fast_row, self._model_fast_input)
        self._write({field: value})

    def _on_api_key_committed(self, value: str) -> None:
        self._writer.run_task(lambda: set_api_key(value))
        self._api_key_control.refresh(has_key=bool(value))

    # -- Privacy pane -----------------------------------------------------

    def _current_sensitive_patterns(self) -> list[str]:
        cfg = load_config()
        patterns = cfg.get("exclude_sensitive_keywords")
        if isinstance(patterns, list) and patterns:
            return [str(p) for p in patterns]
        return list(DEFAULT_SENSITIVE_KEYWORDS)

    def _patterns_helper_html(self) -> str:
        count = len(self._current_sensitive_patterns())
        label = f"{count} pattern{'s' if count != 1 else ''} active"
        return f"{label} \u00b7 <a href='#' style='color:{CORAL}; text-decoration:none;'>Edit patterns</a>"

    def _open_patterns_dialog(self, _href: str) -> None:
        dlg = _PatternsDialog(self._current_sensitive_patterns(), self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._write({"exclude_sensitive_keywords": dlg.patterns()})
            self._exclude_sensitive_row.set_helper_text(self._patterns_helper_html())

    def _build_privacy_pane(self) -> QScrollArea:
        scroll, outer = self._build_pane("Privacy", "What gets stored and copied")
        group = self._new_group(outer)

        self._save_history_row = SettingRow("Save optimization history")
        self._save_history_toggle = ToggleSwitch()
        self._save_history_toggle.toggled.connect(lambda v: self._write({"save_history": v}))
        self._save_history_row.set_control(self._save_history_toggle)
        group.addWidget(self._save_history_row)

        self._exclude_sensitive_row = SettingRow("Skip prompts with sensitive patterns")
        self._exclude_sensitive_row.helper_widget().linkActivated.connect(
            self._open_patterns_dialog
        )
        self._exclude_sensitive_toggle = ToggleSwitch()
        self._exclude_sensitive_toggle.toggled.connect(
            lambda v: self._write({"exclude_sensitive": v})
        )
        self._exclude_sensitive_row.set_control(self._exclude_sensitive_toggle)
        group.addWidget(self._exclude_sensitive_row)

        self._history_limit_row = SettingRow(
            "History limit", "Oldest entries drop past this count"
        )
        self._history_limit_stepper = Stepper(
            PRIVACY_HISTORY_MIN, PRIVACY_HISTORY_MAX, PRIVACY_HISTORY_STEP, 50
        )
        self._history_limit_stepper.valueChanged.connect(
            lambda v: self._write({"history_limit": v})
        )
        self._history_limit_row.set_control(self._history_limit_stepper)
        group.addWidget(self._history_limit_row)

        self._auto_copy_row = SettingRow("Auto-copy optimized output")
        self._auto_copy_toggle = ToggleSwitch()
        self._auto_copy_toggle.toggled.connect(lambda v: self._write({"auto_copy_clipboard": v}))
        self._auto_copy_row.set_control(self._auto_copy_toggle)
        group.addWidget(self._auto_copy_row)

        self._auto_inject_row = SettingRow(
            "Auto-inject into active window", "Simulates a paste. Always asks first."
        )
        self._auto_inject_toggle = ToggleSwitch()
        self._auto_inject_toggle.toggled.connect(
            lambda v: self._write({"auto_inject_enabled": v})
        )
        self._auto_inject_row.set_control(self._auto_inject_toggle)
        group.addWidget(self._auto_inject_row)

        self._voice_enabled_row = SettingRow(
            "Voice input",
            "Shows the mic button on the prompt bar. Push-to-talk while the popup is focused.",
        )
        self._voice_enabled_toggle = ToggleSwitch()
        self._voice_enabled_toggle.toggled.connect(
            lambda v: self._write({"voice_enabled": v})
        )
        self._voice_enabled_row.set_control(self._voice_enabled_toggle)
        group.addWidget(self._voice_enabled_row)

        self._finalize_rows(group)
        outer.addStretch(1)
        return scroll

    # -- Shortcuts pane -----------------------------------------------------

    def _pynput_can_register(self, sequence: str) -> bool:
        try:
            from pynput.keyboard import GlobalHotKeys

            combo = parse_hotkey_to_pynput(sequence)
            listener = GlobalHotKeys({combo: lambda: None})
            listener.start()
            listener.stop()
            return True
        except Exception:
            return False

    def _build_shortcuts_pane(self) -> QScrollArea:
        scroll, outer = self._build_pane("Shortcuts", "Click a binding to record a new one")
        cfg = load_config()

        self._add_eyebrow(outer, "Global")
        global_group = self._new_group(outer)

        self._hotkey_row = SettingRow(
            f"Open or hide {APP_NAME}", control_width=SettingRow.SHORTCUT_CONTROL_WIDTH
        )
        hotkey_cap = KeyCapRow(str(cfg.get("hotkey") or DEFAULT_HOTKEY), is_global=True)
        hotkey_cap.sequence_changed.connect(lambda seq: self._on_shortcut_changed("hotkey", seq))
        self._hotkey_row.set_control(hotkey_cap)
        global_group.addWidget(self._hotkey_row)

        self._hotkey_collapse_row = SettingRow(
            "Collapse to chip", control_width=SettingRow.SHORTCUT_CONTROL_WIDTH
        )
        hotkey_collapse_cap = KeyCapRow(
            str(cfg.get("hotkey_collapse") or DEFAULT_HOTKEY_COLLAPSE), is_global=True
        )
        hotkey_collapse_cap.sequence_changed.connect(
            lambda seq: self._on_shortcut_changed("hotkey_collapse", seq)
        )
        self._hotkey_collapse_row.set_control(hotkey_collapse_cap)
        global_group.addWidget(self._hotkey_collapse_row)
        self._finalize_rows(global_group)

        self._add_eyebrow(outer, "When popup is focused")
        focused_group = self._new_group(outer)

        self._shortcut_collapse_row = SettingRow(
            "Collapse to chip", control_width=SettingRow.SHORTCUT_CONTROL_WIDTH
        )
        shortcut_collapse_cap = KeyCapRow(
            str(cfg.get("shortcut_collapse") or DEFAULT_SHORTCUT_COLLAPSE)
        )
        shortcut_collapse_cap.sequence_changed.connect(
            lambda seq: self._on_shortcut_changed("shortcut_collapse", seq)
        )
        self._shortcut_collapse_row.set_control(shortcut_collapse_cap)
        focused_group.addWidget(self._shortcut_collapse_row)

        self._shortcut_hide_row = SettingRow(
            "Hide to tray", control_width=SettingRow.SHORTCUT_CONTROL_WIDTH
        )
        shortcut_hide_cap = KeyCapRow(
            str(cfg.get("shortcut_hide_tray") or DEFAULT_SHORTCUT_HIDE_TRAY)
        )
        shortcut_hide_cap.sequence_changed.connect(
            lambda seq: self._on_shortcut_changed("shortcut_hide_tray", seq)
        )
        self._shortcut_hide_row.set_control(shortcut_hide_cap)
        focused_group.addWidget(self._shortcut_hide_row)

        self._shortcut_private_row = SettingRow(
            "Toggle private session", control_width=SettingRow.SHORTCUT_CONTROL_WIDTH
        )
        shortcut_private_cap = KeyCapRow(
            str(cfg.get("shortcut_private") or DEFAULT_SHORTCUT_PRIVATE)
        )
        shortcut_private_cap.sequence_changed.connect(
            lambda seq: self._on_shortcut_changed("shortcut_private", seq)
        )
        self._shortcut_private_row.set_control(shortcut_private_cap)
        focused_group.addWidget(self._shortcut_private_row)
        self._finalize_rows(focused_group)

        self._shortcut_caps = {
            "hotkey": hotkey_cap,
            "hotkey_collapse": hotkey_collapse_cap,
            "shortcut_collapse": shortcut_collapse_cap,
            "shortcut_hide_tray": shortcut_hide_cap,
            "shortcut_private": shortcut_private_cap,
        }
        self._shortcut_rows = {
            "hotkey": self._hotkey_row,
            "hotkey_collapse": self._hotkey_collapse_row,
            "shortcut_collapse": self._shortcut_collapse_row,
            "shortcut_hide_tray": self._shortcut_hide_row,
            "shortcut_private": self._shortcut_private_row,
        }
        self._last_good_shortcuts = {k: cap.sequence() for k, cap in self._shortcut_caps.items()}

        outer.addSpacing(10)
        reset_row = QHBoxLayout()
        reset_btn = QPushButton("Reset to defaults")
        reset_btn.setObjectName("linkAction")
        reset_btn.setFont(settings_font(FONT_CAPTION, WEIGHT_MEDIUM))
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setFlat(True)
        reset_btn.clicked.connect(self._reset_shortcuts_to_defaults)
        reset_row.addWidget(reset_btn)
        reset_row.addStretch(1)
        outer.addLayout(reset_row)

        outer.addStretch(1)
        return scroll

    def _on_shortcut_changed(self, key: str, new_seq: str) -> None:
        if key in ("hotkey", "hotkey_collapse") and not self._pynput_can_register(new_seq):
            cap = self._shortcut_caps[key]
            cap.set_sequence(self._last_good_shortcuts[key])
            cap.set_conflict(True, "Already used by another app")
            self._shortcut_rows[key].set_helper_text(
                "Already used by another app", danger=True
            )
            return
        self._last_good_shortcuts[key] = new_seq
        self._write({key: new_seq})
        self._revalidate_shortcuts()

    def _revalidate_shortcuts(self) -> None:
        seqs = {k: cap.sequence() for k, cap in self._shortcut_caps.items()}
        conflicts = compute_shortcut_conflicts(
            seqs["hotkey"],
            seqs["hotkey_collapse"],
            seqs["shortcut_collapse"],
            seqs["shortcut_hide_tray"],
            seqs["shortcut_private"],
        )
        for key, cap in self._shortcut_caps.items():
            is_conflict = conflicts[key]
            reason = "Already used by another binding" if is_conflict else ""
            cap.set_conflict(is_conflict, reason)
            cap.set_registered(not is_conflict)
            self._shortcut_rows[key].set_helper_text(reason, danger=True)

    def _reset_shortcuts_to_defaults(self) -> None:
        defaults = {
            "hotkey": DEFAULT_HOTKEY,
            "hotkey_collapse": DEFAULT_HOTKEY_COLLAPSE,
            "shortcut_collapse": DEFAULT_SHORTCUT_COLLAPSE,
            "shortcut_hide_tray": DEFAULT_SHORTCUT_HIDE_TRAY,
            "shortcut_private": DEFAULT_SHORTCUT_PRIVATE,
        }
        for key, seq in defaults.items():
            self._shortcut_caps[key].set_sequence(seq)
        self._last_good_shortcuts = dict(defaults)
        self._write(dict(defaults))
        self._revalidate_shortcuts()

    # -- Startup pane -----------------------------------------------------

    def _on_start_with_windows_toggled(self, checked: bool) -> None:
        if checked and not is_start_with_windows_enabled():
            enable_start_with_windows()
        elif not checked and is_start_with_windows_enabled():
            disable_start_with_windows()
        self._start_minimized_row.setEnabled(checked)
        self._write({"start_with_windows": checked})

    def _on_check_updates_now(self, _href: str) -> None:
        pass  # stub — not implemented

    def _on_reset_window_position_clicked(self) -> None:
        if self._on_reset_window_position is not None:
            self._on_reset_window_position()

    def _build_startup_pane(self) -> QScrollArea:
        scroll, outer = self._build_pane("Startup", "Launch behavior")
        group = self._new_group(outer)

        self._start_with_windows_row = SettingRow("Start with Windows")
        self._start_with_windows_toggle = ToggleSwitch()
        self._start_with_windows_toggle.toggled.connect(self._on_start_with_windows_toggled)
        self._start_with_windows_row.set_control(self._start_with_windows_toggle)
        group.addWidget(self._start_with_windows_row)

        self._start_minimized_row = SettingRow("Start minimized to tray", indent=True)
        self._start_minimized_toggle = ToggleSwitch()
        self._start_minimized_toggle.toggled.connect(
            lambda v: self._write({"start_minimized_to_tray": v})
        )
        self._start_minimized_row.set_control(self._start_minimized_toggle)
        group.addWidget(self._start_minimized_row)

        self._check_updates_row = SettingRow(
            "Check for updates on launch",
            f"Version {APP_VERSION} \u00b7 "
            f"<a href='#' style='color:{CORAL}; text-decoration:none;'>Check now</a>",
        )
        self._check_updates_row.helper_widget().linkActivated.connect(
            self._on_check_updates_now
        )
        self._check_updates_toggle = ToggleSwitch()
        self._check_updates_toggle.toggled.connect(
            lambda v: self._write({"check_updates_on_launch": v})
        )
        self._check_updates_row.set_control(self._check_updates_toggle)
        group.addWidget(self._check_updates_row)

        self._reset_position_row = SettingRow(
            "Popup position", "If the popup window ever appears off-screen"
        )
        self._reset_position_btn = QPushButton("Reset position", self._reset_position_row)
        self._reset_position_btn.setObjectName("linkAction")
        self._reset_position_btn.setFont(settings_font(FONT_CAPTION, WEIGHT_MEDIUM))
        self._reset_position_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_position_btn.setFlat(True)
        self._reset_position_btn.clicked.connect(self._on_reset_window_position_clicked)
        self._reset_position_row.set_control(self._reset_position_btn)
        group.addWidget(self._reset_position_row)

        self._finalize_rows(group)
        outer.addStretch(1)
        return scroll

    # -- Projects pane (master-detail) ---------------------------------------

    def _sync_project_list_selection(self) -> None:
        current = self._projects_list.currentRow()
        for index in range(self._projects_list.count()):
            widget = self._projects_list.itemWidget(self._projects_list.item(index))
            if isinstance(widget, _ProjectListItem):
                widget.set_selected(index == current)

    def _auto_grow_text_edit(self, edit: QTextEdit, *, min_lines: int = 3) -> None:
        fm = QFontMetrics(edit.font())
        min_height = fm.lineSpacing() * min_lines + 16
        edit.setMinimumHeight(min_height)

        def _resize(*_args: Any) -> None:
            doc_height = edit.document().size().height()
            edit.setFixedHeight(max(min_height, int(doc_height) + 16))

        edit.document().documentLayout().documentSizeChanged.connect(_resize)
        _resize()

    def _build_projects_pane(self) -> QScrollArea:
        scroll, _title_outer = self._build_pane(
            "Projects", "Context injected into every prompt for that project"
        )
        content = scroll.widget()
        outer = content.layout()

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(18)

        list_wrap = QWidget()
        list_wrap.setFixedWidth(180)
        list_col = QVBoxLayout(list_wrap)
        list_col.setContentsMargins(0, 0, 0, 0)
        list_col.setSpacing(0)

        self._projects_list = QListWidget()
        self._projects_list.setObjectName("projectsNavList")
        self._projects_list.setFont(settings_font(FONT_SMALL))
        self._projects_list.currentItemChanged.connect(self._on_project_selected)
        list_col.addWidget(self._projects_list, 1)

        divider = QFrame()
        divider.setObjectName("rowDivider")
        divider.setFixedHeight(1)
        list_col.addWidget(divider)

        new_btn = QPushButton("+ New project")
        new_btn.setObjectName("linkAction")
        new_btn.setFont(settings_font(FONT_CAPTION, WEIGHT_MEDIUM))
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setFlat(True)
        new_btn.clicked.connect(self._on_new_project)
        list_col.addWidget(new_btn)

        body.addWidget(list_wrap, 0)

        detail_wrap = QWidget()
        detail_layout = QVBoxLayout(detail_wrap)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(8)

        header_row = QHBoxLayout()
        self._project_name_label = QLabel("")
        self._project_name_label.setObjectName("projectDetailName")
        self._project_name_label.setFont(settings_font(FONT_SECTION, WEIGHT_MEDIUM))
        header_row.addWidget(self._project_name_label)
        header_row.addStretch(1)
        self._project_delete_btn = QPushButton("Delete")
        self._project_delete_btn.setObjectName("dangerLinkAction")
        self._project_delete_btn.setFont(settings_font(FONT_CAPTION, WEIGHT_MEDIUM))
        self._project_delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._project_delete_btn.clicked.connect(self._on_delete_project)
        header_row.addWidget(self._project_delete_btn)
        detail_layout.addLayout(header_row)

        self._project_saved_label = QLabel("")
        self._project_saved_label.setObjectName("projectDetailSaved")
        self._project_saved_label.setFont(settings_font(FONT_CAPTION))
        detail_layout.addWidget(self._project_saved_label)
        detail_layout.addSpacing(4)

        context_label = QLabel("Context")
        context_label.setObjectName("fieldCaption")
        context_label.setFont(settings_font(FONT_CAPTION, WEIGHT_MEDIUM))
        detail_layout.addWidget(context_label)

        self._project_context_edit = QTextEdit()
        self._project_context_edit.setFont(settings_font(FONT_BODY))
        self._project_context_edit.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._project_context_edit.textChanged.connect(
            lambda: self._on_project_text_changed("conventions", self._project_context_edit)
        )
        detail_layout.addWidget(self._project_context_edit)

        notes_label = QLabel("Notes")
        notes_label.setObjectName("fieldCaption")
        notes_label.setFont(settings_font(FONT_CAPTION, WEIGHT_MEDIUM))
        detail_layout.addWidget(notes_label)

        self._project_notes_edit = QTextEdit()
        self._project_notes_edit.setFont(settings_font(FONT_BODY))
        self._project_notes_edit.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._project_notes_edit.textChanged.connect(
            lambda: self._on_project_text_changed("notes", self._project_notes_edit)
        )
        detail_layout.addWidget(self._project_notes_edit)

        body.addWidget(detail_wrap, 1)
        outer.addLayout(body, 1)

        self._auto_grow_text_edit(self._project_context_edit)
        self._auto_grow_text_edit(self._project_notes_edit)

        self._reload_projects_list()
        return scroll

    def _reload_projects_list(self, *, select_id: str | None = None) -> None:
        self._projects_list.blockSignals(True)
        self._projects_list.clear()
        counts = counts_by_project_name()
        target_row = -1
        for index, project in enumerate(list_projects()):
            project_id = str(project.get("id"))
            name = str(project.get("name") or "Project")
            item = QListWidgetItem(self._projects_list)
            item.setData(Qt.ItemDataRole.UserRole, project_id)
            item_widget = _ProjectListItem(name, counts.get(name, 0))
            item.setSizeHint(item_widget.sizeHint())
            self._projects_list.addItem(item)
            self._projects_list.setItemWidget(item, item_widget)
            if select_id and project_id == select_id:
                target_row = index
        self._projects_list.blockSignals(False)

        if target_row >= 0:
            self._projects_list.setCurrentRow(target_row)
        elif self._projects_list.count() > 0:
            self._projects_list.setCurrentRow(0)
        else:
            self._selected_project_id = None
            self._load_project_detail(None)
        self._sync_project_list_selection()

    def _on_project_selected(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            self._selected_project_id = None
            self._load_project_detail(None)
            return
        project_id = str(current.data(Qt.ItemDataRole.UserRole) or "") or None
        self._selected_project_id = project_id
        self._sync_project_list_selection()
        self._load_project_detail(project_id)

    def _load_project_detail(self, project_id: str | None) -> None:
        self._loading_project_detail = True
        try:
            if project_id is None:
                self._project_name_label.setText("No projects yet")
                self._project_saved_label.setText("")
                self._project_context_edit.setPlainText("")
                self._project_notes_edit.setPlainText("")
                self._project_delete_btn.setEnabled(False)
                self._project_context_edit.setEnabled(False)
                self._project_notes_edit.setEnabled(False)
                return

            project = get_project(project_id)
            if project is None:
                return

            self._project_context_edit.setEnabled(True)
            self._project_notes_edit.setEnabled(True)
            self._project_delete_btn.setEnabled(True)
            self._project_name_label.setText(str(project.get("name") or "Project"))
            self._project_saved_label.setText(
                format_relative_time(str(project.get("updated") or ""))
            )
            self._project_context_edit.setPlainText(str(project.get("conventions") or ""))
            self._project_notes_edit.setPlainText(str(project.get("notes") or ""))
        finally:
            self._loading_project_detail = False

    def _on_project_text_changed(self, field: str, edit: QTextEdit) -> None:
        if self._loading_project_detail or not self._selected_project_id:
            return
        self._pending_project_fields[field] = edit.toPlainText()
        self._project_save_timer.start(400)

    def _flush_project_save(self) -> None:
        project_id = self._selected_project_id
        fields = self._pending_project_fields
        self._pending_project_fields = {}
        if not project_id or not fields:
            return
        self._writer.run_task(lambda: self._persist_project_fields(project_id, fields))

    @staticmethod
    def _persist_project_fields(project_id: str, fields: dict[str, str]) -> str | None:
        project = get_project(project_id)
        if project is None:
            return None
        kwargs = {
            "name": project.get("name", ""),
            "tech_stack": project.get("tech_stack", []),
            "project_type": project.get("project_type", ""),
            "conventions": project.get("conventions", ""),
            "notes": project.get("notes", ""),
        }
        kwargs.update(fields)
        try:
            update_project(project_id, **kwargs)
        except ValueError:
            return None
        return "field_saved"

    def _unique_new_project_name(self) -> str:
        existing = {str(p.get("name", "")).strip().lower() for p in list_projects()}
        base = "New project"
        if base.lower() not in existing:
            return base
        n = 2
        while f"{base} {n}".lower() in existing:
            n += 1
        return f"{base} {n}"

    def _on_new_project(self) -> None:
        name = self._unique_new_project_name()
        self._pending_new_project = True
        self._writer.run_task(lambda: create_project(name=name))

    def _on_delete_project(self) -> None:
        project_id = self._selected_project_id
        if not project_id:
            return
        project = get_project(project_id)
        name = str(project.get("name") or "this project") if project else "this project"
        confirm = QMessageBox.question(
            self,
            "Delete project",
            f'Delete "{name}"? This removes its context and notes, and cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._pending_delete_project = True
        self._writer.run_task(lambda: self._delete_project_task(project_id))

    @staticmethod
    def _delete_project_task(project_id: str) -> str:
        try:
            delete_project(project_id)
        except ValueError:
            pass
        return "deleted"

    def _on_project_task_done(self, result: Any) -> None:
        if self._pending_delete_project:
            self._pending_delete_project = False
            self._selected_project_id = None
            self._reload_projects_list()
        elif self._pending_new_project:
            self._pending_new_project = False
            if isinstance(result, str):
                self._reload_projects_list(select_id=result)
        elif self._selected_project_id:
            self._project_saved_label.setText("Saved just now")
        if self._on_saved is not None:
            self._on_saved()

    # -- misc ----------------------------------------------------------------

    def _on_nav_changed(self, row: int) -> None:
        if row < 0:
            return
        self._stack.setCurrentIndex(row)

    def _wire_tab_order(self) -> None:
        """Keyboard navigation follows visual order; the sidebar is reachable."""
        QWidget.setTabOrder(self._nav, self._provider_combo)
        QWidget.setTabOrder(self._provider_combo, self._api_key_control)
        QWidget.setTabOrder(self._api_key_control, self._model_input)
        QWidget.setTabOrder(self._model_input, self._model_fast_input)
        QWidget.setTabOrder(self._model_fast_input, self._persist_draft_toggle)
        QWidget.setTabOrder(self._persist_draft_toggle, self._save_history_toggle)
        QWidget.setTabOrder(self._save_history_toggle, self._exclude_sensitive_toggle)
        QWidget.setTabOrder(self._exclude_sensitive_toggle, self._history_limit_stepper)
        QWidget.setTabOrder(self._history_limit_stepper, self._auto_copy_toggle)
        QWidget.setTabOrder(self._auto_copy_toggle, self._auto_inject_toggle)
        QWidget.setTabOrder(self._auto_inject_toggle, self._voice_enabled_toggle)
        QWidget.setTabOrder(self._voice_enabled_toggle, self._start_with_windows_toggle)
        QWidget.setTabOrder(self._start_with_windows_toggle, self._start_minimized_toggle)
        QWidget.setTabOrder(self._start_minimized_toggle, self._check_updates_toggle)
        QWidget.setTabOrder(self._check_updates_toggle, self._reset_position_btn)
        QWidget.setTabOrder(self._reset_position_btn, self._projects_list)
        QWidget.setTabOrder(self._projects_list, self._project_context_edit)
        QWidget.setTabOrder(self._project_context_edit, self._project_notes_edit)

    def _load_all(self) -> None:
        cfg = load_config()
        provider = get_provider()

        self._provider_combo.blockSignals(True)
        idx = self._provider_combo.findData(provider)
        self._provider_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._provider_combo.blockSignals(False)

        self._api_key_control.refresh(has_key=has_api_key())

        self._model_input.blockSignals(True)
        self._model_input.setText(str(cfg.get("model") or PROVIDER_PRESETS[provider]["model"]))
        self._model_input.blockSignals(False)
        self._validate_model_field(self._model_row, self._model_input)

        self._model_fast_input.blockSignals(True)
        self._model_fast_input.setText(
            str(cfg.get("model_fast") or PROVIDER_PRESETS[provider]["model_fast"])
        )
        self._model_fast_input.blockSignals(False)
        self._validate_model_field(self._model_fast_row, self._model_fast_input)

        self._persist_draft_toggle.set_checked_silent(bool(cfg.get("persist_draft", True)))

        self._save_history_toggle.set_checked_silent(bool(cfg.get("save_history", True)))
        self._exclude_sensitive_toggle.set_checked_silent(bool(cfg.get("exclude_sensitive", False)))
        self._exclude_sensitive_row.set_helper_text(self._patterns_helper_html())
        self._history_limit_stepper.setValue(int(cfg.get("history_limit") or 50), emit=False)
        self._auto_copy_toggle.set_checked_silent(bool(cfg.get("auto_copy_clipboard", True)))
        self._auto_inject_toggle.set_checked_silent(bool(cfg.get("auto_inject_enabled", False)))
        self._voice_enabled_toggle.set_checked_silent(bool(cfg.get("voice_enabled", False)))

        self._start_with_windows_toggle.set_checked_silent(is_start_with_windows_enabled())
        self._start_minimized_row.setEnabled(self._start_with_windows_toggle.isChecked())
        self._start_minimized_toggle.set_checked_silent(
            bool(cfg.get("start_minimized_to_tray", True))
        )
        self._check_updates_toggle.set_checked_silent(
            bool(cfg.get("check_updates_on_launch", False))
        )

        self._revalidate_shortcuts()

    @staticmethod
    def run_if_needed(parent: QWidget | None = None) -> bool:
        """Show settings when no API key is configured (first-run flow)."""
        if has_api_key():
            return True
        dlg = SettingsDialog(parent, first_run=True)
        dlg.exec()
        return has_api_key()


SetupDialog = SettingsDialog
