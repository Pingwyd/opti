"""
PyQt6 settings dialog for MetaPrompt configuration.
"""

from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import (
    DEFAULT_HOTKEY,
    DEFAULT_HOTKEY_COLLAPSE,
    DEFAULT_SHORTCUT_COLLAPSE,
    DEFAULT_SHORTCUT_HIDE_TRAY,
    DEFAULT_SHORTCUT_PRIVATE,
    PROVIDER_PRESETS,
    RESCUE_WINDOW_SHORTCUT,
    VALID_PROVIDERS,
    get_provider,
    has_api_key,
    global_hotkeys_conflict,
    hotkey_conflicts_with_shortcuts,
    in_app_shortcuts_conflict,
    load_config,
    normalize_hotkey_string,
    normalize_shortcut_string,
    save_config,
    set_api_key,
)
from startup import (
    disable_start_with_windows,
    enable_start_with_windows,
    is_start_with_windows_enabled,
)
from projects import (
    PROJECT_TYPES,
    create_project,
    delete_project,
    list_projects,
    parse_tech_stack_input,
    update_project,
)
from ui_theme import settings_stylesheet

HISTORY_LIMIT_MIN = 50
HISTORY_LIMIT_MAX = 5000
_SPACING = 12
_GROUP_SPACING = 16
_FIELD_SPACING = 10


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
    history_limit: int,
    start_with_windows: bool,
    shortcut_collapse: str,
    shortcut_hide_tray: str,
    shortcut_private: str,
    auto_copy_clipboard: bool,
    include_project_context_in_private: bool = False,
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
        "history_limit": max(HISTORY_LIMIT_MIN, min(HISTORY_LIMIT_MAX, history_limit)),
        "start_with_windows": start_with_windows,
        "shortcut_collapse": normalize_shortcut_string(
            shortcut_collapse, DEFAULT_SHORTCUT_COLLAPSE
        ),
        "shortcut_hide_tray": normalize_shortcut_string(
            shortcut_hide_tray, DEFAULT_SHORTCUT_HIDE_TRAY
        ),
        "shortcut_private": normalize_shortcut_string(
            shortcut_private, DEFAULT_SHORTCUT_PRIVATE
        ),
        "auto_copy_clipboard": auto_copy_clipboard,
        "include_project_context_in_private": include_project_context_in_private,
    }


def apply_settings_values(values: dict[str, Any], *, require_api_key: bool = False) -> str | None:
    """
    Persist settings to config.json and sync Windows startup.

    Returns an error message on validation failure, else None.
    """
    api_key_input = str(values.get("api_key_input") or "")
    if require_api_key and not api_key_input and not has_api_key():
        return "API key cannot be empty."

    provider = str(values.get("provider") or "gemini").lower().strip()
    if provider not in VALID_PROVIDERS:
        return f"Unknown provider: {provider}"

    shortcut_collapse = normalize_shortcut_string(
        str(values.get("shortcut_collapse") or ""),
        DEFAULT_SHORTCUT_COLLAPSE,
    )
    shortcut_hide_tray = normalize_shortcut_string(
        str(values.get("shortcut_hide_tray") or ""),
        DEFAULT_SHORTCUT_HIDE_TRAY,
    )
    shortcut_private = normalize_shortcut_string(
        str(values.get("shortcut_private") or ""),
        DEFAULT_SHORTCUT_PRIVATE,
    )
    hotkey = normalize_hotkey_string(str(values.get("hotkey") or ""), DEFAULT_HOTKEY)
    hotkey_collapse = normalize_hotkey_string(
        str(values.get("hotkey_collapse") or ""),
        DEFAULT_HOTKEY_COLLAPSE,
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
    cfg["history_limit"] = int(values.get("history_limit") or 50)
    cfg["start_with_windows"] = bool(values.get("start_with_windows", False))
    cfg["shortcut_collapse"] = shortcut_collapse
    cfg["shortcut_hide_tray"] = shortcut_hide_tray
    cfg["shortcut_private"] = shortcut_private
    cfg["auto_copy_clipboard"] = bool(values.get("auto_copy_clipboard", True))
    cfg["include_project_context_in_private"] = bool(
        values.get("include_project_context_in_private", False)
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


class TagInputWidget(QWidget):
    """Tech-stack tag editor: type + Enter or comma to add, × to remove."""

    tags_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._input = QLineEdit(self)
        self._input.setPlaceholderText(
            "Type a technology and press Enter, or separate with commas"
        )
        self._input.setMinimumHeight(36)
        self._input.returnPressed.connect(self._add_from_input)
        self._input.textChanged.connect(self._on_input_changed)
        layout.addWidget(self._input)

        self._list = QListWidget(self)
        self._list.setObjectName("tagList")
        self._list.setFlow(QListWidget.Flow.LeftToRight)
        self._list.setWrapping(True)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.setMaximumHeight(120)
        layout.addWidget(self._list)

    def tags(self) -> list[str]:
        result: list[str] = []
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item is None:
                continue
            text = str(item.data(Qt.ItemDataRole.UserRole) or item.text() or "").strip()
            if text:
                result.append(text)
        return result

    def set_tags(self, tags: list[str]) -> None:
        self._list.clear()
        added = False
        for tag in tags:
            if self._add_tag(tag, emit=False):
                added = True
        self._refresh_tag_layout()
        if added:
            self.tags_changed.emit()

    def _add_from_input(self) -> None:
        text = self._input.text()
        tokens = parse_tech_stack_input(text)
        if not tokens:
            return
        self._input.blockSignals(True)
        self._input.clear()
        self._input.blockSignals(False)
        self._add_tags(tokens)

    def _on_input_changed(self, text: str) -> None:
        if "," not in text and "\n" not in text:
            return
        if text.endswith(",") or text.endswith("\n"):
            complete, remainder = text, ""
        else:
            last_sep = max(text.rfind(","), text.rfind("\n"))
            if last_sep < 0:
                return
            complete = text[: last_sep + 1]
            remainder = text[last_sep + 1 :]
        tokens = parse_tech_stack_input(complete)
        if not tokens:
            return
        self._input.blockSignals(True)
        self._input.setText(remainder)
        self._input.blockSignals(False)
        self._add_tags(tokens)

    def _add_tags(self, tags: list[str]) -> None:
        added = False
        for tag in tags:
            if self._add_tag(tag, emit=False):
                added = True
        if added:
            self._refresh_tag_layout()
            self.tags_changed.emit()

    def _add_tag(self, text: str, *, emit: bool = True) -> bool:
        normalized = text.strip()
        if not normalized:
            return False
        if normalized.lower() in {t.lower() for t in self.tags()}:
            return False
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, normalized)
        self._list.addItem(item)
        chip = QWidget(self._list)
        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(8, 4, 4, 4)
        chip_layout.setSpacing(4)
        label = QLabel(normalized, chip)
        label.setObjectName("tagChipLabel")
        remove_btn = QPushButton("×", chip)
        remove_btn.setObjectName("tagRemoveBtn")
        remove_btn.setFixedSize(18, 18)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(lambda _checked=False, it=item: self._remove_item(it))
        chip_layout.addWidget(label)
        chip_layout.addWidget(remove_btn)
        self._list.setItemWidget(item, chip)
        if emit:
            self._refresh_tag_layout()
            self.tags_changed.emit()
        return True

    def _refresh_tag_layout(self) -> None:
        self._list.scheduleDelayedItemsLayout()
        self._list.updateGeometry()

    def _remove_item(self, item: QListWidgetItem) -> None:
        row = self._list.row(item)
        if row >= 0:
            self._list.takeItem(row)
            self._refresh_tag_layout()
            self.tags_changed.emit()


class SettingsDialog(QDialog):
    """Application settings: provider, models, behavior, and startup."""

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
        self._provider_changing = False
        self._on_saved = on_saved
        self._on_reset_window_position = on_reset_window_position
        self._initial_tab = initial_tab
        self._new_project = new_project
        self._selected_project_id: str | None = None
        self._projects_is_new = False

        self.setWindowTitle("MetaPrompt setup" if first_run else "MetaPrompt settings")
        self.setModal(True)
        self.resize(560, 620)
        self.setMinimumWidth(500)
        self.setMinimumHeight(480)

        self._build_ui()
        self.setStyleSheet(settings_stylesheet())
        self._load_from_config()
        self._wire_tab_order()

        if self._new_project:
            self._projects_new()

        if self._focus_api_key:
            self._api_key_input.setFocus()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 20)
        root.setSpacing(_SPACING)

        title = QLabel("Connect your API key" if self._first_run else "Settings", self)
        title.setObjectName("settingsTitle")
        root.addWidget(title)

        if self._first_run:
            subtitle = QLabel(
                "Gemini is the default (free tier). Your key stays on this device "
                "and is only sent to your chosen provider.",
                self,
            )
            subtitle.setObjectName("settingsSubtitle")
            subtitle.setWordWrap(True)
            root.addWidget(subtitle)

        self._tabs = QTabWidget(self)
        self._tabs.setObjectName("settingsTabs")
        self._tabs.setDocumentMode(True)

        self._tabs.addTab(self._build_general_tab(), "General")
        self._tabs.addTab(self._build_models_tab(), "Models")
        self._tabs.addTab(self._build_privacy_tab(), "Privacy")
        self._tabs.addTab(self._build_shortcuts_tab(), "Shortcuts")
        self._tabs.addTab(self._build_startup_tab(), "Startup")
        self._projects_tab = self._build_projects_tab()
        self._tabs.addTab(self._projects_tab, "Projects")

        if self._first_run:
            for index in range(1, self._tabs.count()):
                self._tabs.setTabVisible(index, False)

        if self._initial_tab == "projects":
            projects_index = self._tabs.indexOf(self._projects_tab)
            if projects_index >= 0:
                self._tabs.setCurrentIndex(projects_index)

        root.addWidget(self._tabs, stretch=1)

        self._error = QLabel("", self)
        self._error.setObjectName("errorLabel")
        self._error.hide()
        root.addWidget(self._error)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        if not self._first_run:
            cancel_btn = QPushButton("Cancel", self)
            cancel_btn.setObjectName("cancelBtn")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.setMinimumHeight(36)
            cancel_btn.clicked.connect(self.reject)
            btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save and continue" if self._first_run else "Save", self)
        save_btn.setObjectName("saveBtn")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setMinimumHeight(36)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        root.addLayout(btn_row)

        self._api_key_input.returnPressed.connect(self._on_save)

    def _scroll_tab(self, body: QWidget) -> QWidget:
        """Wrap tab content in a scroll area for long forms."""
        scroll = QScrollArea(self)
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        return scroll

    def _tab_body(self) -> QWidget:
        body = QWidget(self)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(4, 8, 8, 8)
        layout.setSpacing(_GROUP_SPACING)
        body._layout = layout  # type: ignore[attr-defined]
        return body

    @staticmethod
    def _field_label(text: str, parent: QWidget, *, buddy: QWidget | None = None) -> QLabel:
        label = QLabel(text, parent)
        label.setObjectName("fieldLabel")
        if buddy is not None:
            label.setBuddy(buddy)
        return label

    @staticmethod
    def _hint_label(text: str, parent: QWidget) -> QLabel:
        hint = QLabel(text, parent)
        hint.setObjectName("fieldHint")
        hint.setWordWrap(True)
        return hint

    @staticmethod
    def _tab_description(text: str, parent: QWidget) -> QLabel:
        desc = QLabel(text, parent)
        desc.setObjectName("tabDescription")
        desc.setWordWrap(True)
        return desc

    @staticmethod
    def _group_box(title: str, parent: QWidget) -> QGroupBox:
        group = QGroupBox(title, parent)
        group.setObjectName("settingsGroup")
        return group

    def _add_key_edit(
        self,
        layout: QVBoxLayout,
        label_text: str,
        default: str,
        parent: QWidget,
    ) -> QKeySequenceEdit:
        edit = QKeySequenceEdit(QKeySequence(default), parent)
        edit.setObjectName("shortcutEdit")
        edit.setMinimumHeight(36)
        layout.addWidget(self._field_label(label_text, parent, buddy=edit))
        layout.addWidget(edit)
        return edit

    def _build_general_tab(self) -> QWidget:
        body = self._tab_body()
        layout: QVBoxLayout = body._layout  # type: ignore[attr-defined]
        layout.addWidget(
            self._tab_description("API connection and default behavior", body)
        )
        connection = self._group_box("Connection", body)
        conn_layout = QVBoxLayout(connection)
        conn_layout.setContentsMargins(16, 20, 16, 16)
        conn_layout.setSpacing(_FIELD_SPACING)

        self._provider_combo = QComboBox(connection)
        self._provider_combo.setMinimumHeight(36)
        for provider_id in VALID_PROVIDERS:
            self._provider_combo.addItem(PROVIDER_PRESETS[provider_id]["label"], provider_id)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        conn_layout.addWidget(self._field_label("Provider", connection, buddy=self._provider_combo))
        conn_layout.addWidget(self._provider_combo)

        self._api_key_input = QLineEdit(connection)
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText("Paste key here (leave blank to keep current)")
        self._api_key_input.setMinimumHeight(36)
        conn_layout.addWidget(self._field_label("API key", connection, buddy=self._api_key_input))
        conn_layout.addWidget(self._api_key_input)

        layout.addWidget(connection)

        behavior = self._group_box("Default behavior", body)
        behavior_layout = QVBoxLayout(behavior)
        behavior_layout.setContentsMargins(16, 20, 16, 16)
        behavior_layout.setSpacing(_FIELD_SPACING)

        self._mode_combo = QComboBox(behavior)
        self._mode_combo.setMinimumHeight(36)
        self._mode_combo.addItem("Thorough", "thorough")
        self._mode_combo.addItem("Fast", "fast")
        behavior_layout.addWidget(self._field_label("Default mode", behavior, buddy=self._mode_combo))
        behavior_layout.addWidget(self._mode_combo)

        self._persist_draft_cb = QCheckBox("Remember draft text between sessions", behavior)
        behavior_layout.addWidget(self._persist_draft_cb)

        layout.addWidget(behavior)

        window_group = self._group_box("Window position", body)
        window_layout = QVBoxLayout(window_group)
        window_layout.setContentsMargins(16, 20, 16, 16)
        window_layout.setSpacing(_FIELD_SPACING)
        window_layout.addWidget(
            self._hint_label(
                "If MetaPrompt ends up off-screen after a monitor change, reset it "
                f"to the center of your primary display. With the popup focused, "
                f"you can also press {RESCUE_WINDOW_SHORTCUT}.",
                window_group,
            )
        )
        reset_btn = QPushButton("Reset window position", window_group)
        reset_btn.setObjectName("saveBtn")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setMinimumHeight(36)
        reset_btn.clicked.connect(self._on_reset_window_position_clicked)
        window_layout.addWidget(reset_btn)
        self._window_reset_status = QLabel("", window_group)
        self._window_reset_status.setObjectName("fieldHint")
        self._window_reset_status.hide()
        window_layout.addWidget(self._window_reset_status)
        layout.addWidget(window_group)
        if self._first_run:
            window_group.hide()

        hotkey_note = self._group_box("Global hotkey", body)
        note_layout = QVBoxLayout(hotkey_note)
        note_layout.setContentsMargins(16, 20, 16, 16)
        note_layout.setSpacing(_FIELD_SPACING)
        note_layout.addWidget(
            self._hint_label(
                "The system-wide shortcuts to open or collapse MetaPrompt are configured under "
                "the Shortcuts tab. On macOS, grant Accessibility to this app.",
                hotkey_note,
            )
        )
        layout.addWidget(hotkey_note)

        layout.addStretch()
        return self._scroll_tab(body)

    def _build_models_tab(self) -> QWidget:
        body = self._tab_body()
        layout: QVBoxLayout = body._layout  # type: ignore[attr-defined]
        layout.addWidget(self._tab_description("LLM model IDs per provider", body))
        models = self._group_box("Model IDs", body)
        models_layout = QVBoxLayout(models)
        models_layout.setContentsMargins(16, 20, 16, 16)
        models_layout.setSpacing(_FIELD_SPACING)

        self._model_input = QLineEdit(models)
        self._model_input.setMinimumHeight(36)
        models_layout.addWidget(self._field_label("Thorough model", models, buddy=self._model_input))
        models_layout.addWidget(self._model_input)

        self._model_fast_input = QLineEdit(models)
        self._model_fast_input.setMinimumHeight(36)
        models_layout.addWidget(
            self._field_label("Fast model", models, buddy=self._model_fast_input)
        )
        models_layout.addWidget(self._model_fast_input)

        models_layout.addWidget(
            self._hint_label(
                "Changing provider resets these to that provider's defaults. "
                "Override only if you know the exact model ID.",
                models,
            )
        )

        layout.addWidget(models)
        layout.addStretch()
        return self._scroll_tab(body)

    def _build_privacy_tab(self) -> QWidget:
        body = self._tab_body()
        layout: QVBoxLayout = body._layout  # type: ignore[attr-defined]
        layout.addWidget(self._tab_description("History and clipboard", body))
        history = self._group_box("History", body)
        history_layout = QVBoxLayout(history)
        history_layout.setContentsMargins(16, 20, 16, 16)
        history_layout.setSpacing(_FIELD_SPACING)

        self._save_history_cb = QCheckBox("Save optimization history", history)
        history_layout.addWidget(self._save_history_cb)

        self._exclude_sensitive_cb = QCheckBox(
            "Don't save prompts containing sensitive patterns", history
        )
        history_layout.addWidget(self._exclude_sensitive_cb)

        limit_row = QHBoxLayout()
        self._history_limit_spin = QSpinBox(history)
        self._history_limit_spin.setRange(HISTORY_LIMIT_MIN, HISTORY_LIMIT_MAX)
        self._history_limit_spin.setSingleStep(50)
        self._history_limit_spin.setMinimumHeight(36)
        limit_row.addWidget(self._field_label("History limit", history, buddy=self._history_limit_spin))
        limit_row.addStretch()
        limit_row.addWidget(self._history_limit_spin)
        history_layout.addLayout(limit_row)

        layout.addWidget(history)

        clipboard = self._group_box("Clipboard", body)
        clipboard_layout = QVBoxLayout(clipboard)
        clipboard_layout.setContentsMargins(16, 20, 16, 16)
        clipboard_layout.setSpacing(_FIELD_SPACING)

        self._auto_copy_cb = QCheckBox(
            "Automatically copy optimized output to clipboard", clipboard
        )
        clipboard_layout.addWidget(self._auto_copy_cb)

        project_privacy = self._group_box("Project context", body)
        project_privacy_layout = QVBoxLayout(project_privacy)
        project_privacy_layout.setContentsMargins(16, 20, 16, 16)
        project_privacy_layout.setSpacing(_FIELD_SPACING)

        self._include_project_private_cb = QCheckBox(
            "Include project context in private mode", project_privacy
        )
        project_privacy_layout.addWidget(
            self._hint_label(
                "When private session is on, project context is excluded from the "
                "system prompt by default.",
                project_privacy,
            )
        )
        project_privacy_layout.addWidget(self._include_project_private_cb)

        layout.addWidget(clipboard)
        layout.addWidget(project_privacy)
        layout.addStretch()
        return self._scroll_tab(body)

    def _build_shortcuts_tab(self) -> QWidget:
        body = self._tab_body()
        layout: QVBoxLayout = body._layout  # type: ignore[attr-defined]
        layout.addWidget(
            self._tab_description("Global and in-app keyboard shortcuts", body)
        )

        global_group = self._group_box("Global (system-wide)", body)
        global_layout = QVBoxLayout(global_group)
        global_layout.setContentsMargins(16, 20, 16, 16)
        global_layout.setSpacing(_FIELD_SPACING)

        self._global_hotkey_edit = self._add_key_edit(
            global_layout,
            "Open / hide MetaPrompt (system-wide)",
            DEFAULT_HOTKEY,
            global_group,
        )
        self._global_collapse_hotkey_edit = self._add_key_edit(
            global_layout,
            "Collapse to chip (global)",
            DEFAULT_HOTKEY_COLLAPSE,
            global_group,
        )
        global_layout.addWidget(
            self._hint_label(
                "Works system-wide. Open hotkey toggles show/hide (expanded or chip). "
                "Collapse hotkey toggles chip ↔ expanded; when hidden, shows as chip. "
                "On macOS, grant Accessibility to this app. Restart not required.",
                global_group,
            )
        )

        layout.addWidget(global_group)

        popup_group = self._group_box("When popup is focused (in-app)", body)
        popup_layout = QVBoxLayout(popup_group)
        popup_layout.setContentsMargins(16, 20, 16, 16)
        popup_layout.setSpacing(_FIELD_SPACING)

        self._collapse_shortcut_edit = self._add_key_edit(
            popup_layout,
            "Collapse to chip (when popup focused)",
            DEFAULT_SHORTCUT_COLLAPSE,
            popup_group,
        )
        self._hide_shortcut_edit = self._add_key_edit(
            popup_layout,
            "Hide to tray",
            DEFAULT_SHORTCUT_HIDE_TRAY,
            popup_group,
        )
        self._private_shortcut_edit = self._add_key_edit(
            popup_layout,
            "Toggle private session",
            DEFAULT_SHORTCUT_PRIVATE,
            popup_group,
        )
        popup_layout.addWidget(
            self._hint_label(
                "These shortcuts work while the MetaPrompt popup has focus. "
                f"Rescue off-screen windows with {RESCUE_WINDOW_SHORTCUT} "
                "(not configurable).",
                popup_group,
            )
        )

        layout.addWidget(popup_group)
        layout.addStretch()
        return self._scroll_tab(body)

    def _build_startup_tab(self) -> QWidget:
        body = self._tab_body()
        layout: QVBoxLayout = body._layout  # type: ignore[attr-defined]
        layout.addWidget(self._tab_description("Launch options", body))
        startup = self._group_box("Windows startup", body)
        startup_layout = QVBoxLayout(startup)
        startup_layout.setContentsMargins(16, 20, 16, 16)
        startup_layout.setSpacing(_FIELD_SPACING)

        self._startup_cb = QCheckBox("Start MetaPrompt with Windows", startup)
        startup_layout.addWidget(self._startup_cb)

        layout.addWidget(startup)
        layout.addStretch()
        return self._scroll_tab(body)

    def _build_projects_tab(self) -> QWidget:
        body = self._tab_body()
        layout: QVBoxLayout = body._layout  # type: ignore[attr-defined]
        layout.addWidget(
            self._tab_description("Reusable context for optimizations", body)
        )
        splitter = QSplitter(Qt.Orientation.Horizontal, body)
        splitter.setObjectName("projectsSplitter")

        list_panel = QWidget(splitter)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 8, 0)
        list_layout.setSpacing(8)

        list_header = QHBoxLayout()
        list_label = QLabel("Projects", list_panel)
        list_label.setObjectName("fieldLabel")
        list_header.addWidget(list_label)
        list_header.addStretch()
        new_btn = QPushButton("+ New", list_panel)
        new_btn.setObjectName("saveBtn")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._projects_new)
        list_header.addWidget(new_btn)
        list_layout.addLayout(list_header)

        self._projects_list = QListWidget(list_panel)
        self._projects_list.setObjectName("projectsList")
        self._projects_list.currentItemChanged.connect(self._on_project_selected)
        list_layout.addWidget(self._projects_list, stretch=1)

        form_panel = QWidget(splitter)
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(8, 0, 0, 0)
        form_layout.setSpacing(_FIELD_SPACING)

        form_group = self._group_box("Project details", form_panel)
        fields = QVBoxLayout(form_group)
        fields.setContentsMargins(16, 20, 16, 16)
        fields.setSpacing(_FIELD_SPACING)

        self._project_name_input = QLineEdit(form_group)
        self._project_name_input.setMinimumHeight(36)
        self._project_name_input.textChanged.connect(self._sync_project_list_preview)
        fields.addWidget(
            self._field_label("Name", form_group, buddy=self._project_name_input)
        )
        fields.addWidget(self._project_name_input)

        self._project_tags = TagInputWidget(form_group)
        self._project_tags.tags_changed.connect(self._sync_project_list_preview)
        fields.addWidget(self._field_label("Tech stack", form_group))
        fields.addWidget(self._project_tags)

        self._project_type_combo = QComboBox(form_group)
        self._project_type_combo.setMinimumHeight(36)
        self._project_type_combo.addItem("(none)", "")
        for ptype in PROJECT_TYPES:
            if ptype:
                self._project_type_combo.addItem(ptype, ptype)
        fields.addWidget(
            self._field_label("Project type", form_group, buddy=self._project_type_combo)
        )
        fields.addWidget(self._project_type_combo)

        self._project_conventions = QTextEdit(form_group)
        self._project_conventions.setPlaceholderText("How we do things here…")
        self._project_conventions.setMinimumHeight(72)
        fields.addWidget(self._field_label("Conventions", form_group))
        fields.addWidget(self._project_conventions)

        self._project_notes = QTextEdit(form_group)
        self._project_notes.setPlaceholderText("Additional notes…")
        self._project_notes.setMinimumHeight(72)
        fields.addWidget(self._field_label("Notes", form_group))
        fields.addWidget(self._project_notes)

        form_layout.addWidget(form_group)

        self._projects_error = QLabel("", form_panel)
        self._projects_error.setObjectName("errorLabel")
        self._projects_error.hide()
        form_layout.addWidget(self._projects_error)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._project_delete_btn = QPushButton("Delete", form_panel)
        self._project_delete_btn.setObjectName("cancelBtn")
        self._project_delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._project_delete_btn.clicked.connect(self._projects_delete)
        btn_row.addWidget(self._project_delete_btn)

        cancel_btn = QPushButton("Cancel", form_panel)
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self._projects_cancel_form)
        btn_row.addWidget(cancel_btn)

        save_project_btn = QPushButton("Save project", form_panel)
        save_project_btn.setObjectName("saveBtn")
        save_project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_project_btn.clicked.connect(self._projects_save)
        btn_row.addWidget(save_project_btn)
        form_layout.addLayout(btn_row)
        form_layout.addStretch()

        splitter.addWidget(list_panel)
        splitter.addWidget(form_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

        self._reload_projects_list()
        return self._scroll_tab(body)

    def _format_project_list_label(
        self,
        *,
        name: str,
        tech_stack: list[str] | None = None,
        last_used: str = "",
    ) -> str:
        display_name = name.strip() or "Project"
        lines = [display_name]
        tags = [t.strip() for t in (tech_stack or []) if str(t).strip()]
        if tags:
            lines.append(", ".join(tags))
        if last_used:
            lines.append(f"Last used {last_used[:10]}")
        return "\n".join(lines)

    def _format_project_list_label_from_project(self, project: dict[str, Any]) -> str:
        return self._format_project_list_label(
            name=str(project.get("name") or project.get("id") or "Project"),
            tech_stack=list(project.get("tech_stack") or []),
            last_used=str(project.get("last_used") or ""),
        )

    def _sync_project_list_preview(self) -> None:
        current = self._projects_list.currentItem()
        if current is None:
            return
        current.setText(
            self._format_project_list_label(
                name=self._project_name_input.text(),
                tech_stack=self._project_tags.tags(),
            )
        )

    def _reload_projects_list(self, *, select_id: str | None = None) -> None:
        self._projects_list.blockSignals(True)
        self._projects_list.clear()
        for project in list_projects():
            item = QListWidgetItem(self._format_project_list_label_from_project(project))
            item.setData(Qt.ItemDataRole.UserRole, str(project.get("id")))
            self._projects_list.addItem(item)
            if select_id and str(project.get("id")) == select_id:
                self._projects_list.setCurrentItem(item)
        self._projects_list.blockSignals(False)
        if select_id is None and self._projects_list.count() > 0:
            self._projects_list.setCurrentRow(0)

    def _clear_project_form(self) -> None:
        self._project_name_input.clear()
        self._project_tags.set_tags([])
        self._project_type_combo.setCurrentIndex(0)
        self._project_conventions.clear()
        self._project_notes.clear()
        self._projects_error.hide()

    def _load_project_form(self, project_id: str) -> None:
        from projects import get_project

        project = get_project(project_id)
        if project is None:
            return
        self._selected_project_id = project_id
        self._projects_is_new = False
        self._project_name_input.setText(str(project.get("name") or ""))
        self._project_tags.set_tags(list(project.get("tech_stack") or []))
        ptype = str(project.get("project_type") or "")
        idx = self._project_type_combo.findData(ptype)
        self._project_type_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._project_conventions.setPlainText(str(project.get("conventions") or ""))
        self._project_notes.setPlainText(str(project.get("notes") or ""))
        self._project_delete_btn.setEnabled(True)
        self._projects_error.hide()

    def _on_project_selected(self, current: QListWidgetItem | None, _previous) -> None:  # noqa: ANN001
        if current is None:
            return
        project_id = str(current.data(Qt.ItemDataRole.UserRole) or "")
        if project_id:
            self._load_project_form(project_id)

    def _projects_new(self) -> None:
        self._selected_project_id = None
        self._projects_is_new = True
        self._projects_list.clearSelection()
        self._clear_project_form()
        self._project_delete_btn.setEnabled(False)
        self._project_name_input.setFocus()

    def _projects_cancel_form(self) -> None:
        if self._selected_project_id:
            self._load_project_form(self._selected_project_id)
            return
        self._projects_new()

    def _projects_form_values(self) -> dict[str, Any]:
        return {
            "name": self._project_name_input.text().strip(),
            "tech_stack": self._project_tags.tags(),
            "project_type": str(self._project_type_combo.currentData() or ""),
            "conventions": self._project_conventions.toPlainText().strip(),
            "notes": self._project_notes.toPlainText().strip(),
        }

    def _projects_save(self) -> None:
        values = self._projects_form_values()
        try:
            if self._projects_is_new or not self._selected_project_id:
                project_id = create_project(**values)
                self._projects_is_new = False
                self._selected_project_id = project_id
            else:
                update_project(self._selected_project_id, **values)
                project_id = self._selected_project_id
        except ValueError as exc:
            self._projects_error.setText(str(exc))
            self._projects_error.show()
            return

        self._projects_error.hide()
        self._reload_projects_list(select_id=project_id)
        if self._on_saved is not None:
            self._on_saved()

    def _projects_delete(self) -> None:
        if not self._selected_project_id:
            return
        try:
            delete_project(self._selected_project_id)
        except ValueError as exc:
            self._projects_error.setText(str(exc))
            self._projects_error.show()
            return
        self._selected_project_id = None
        self._projects_is_new = False
        self._reload_projects_list()
        self._projects_new()
        if self._on_saved is not None:
            self._on_saved()

    def _wire_tab_order(self) -> None:
        """Keyboard navigation order across visible controls."""
        QWidget.setTabOrder(self._provider_combo, self._api_key_input)
        QWidget.setTabOrder(self._api_key_input, self._mode_combo)
        QWidget.setTabOrder(self._mode_combo, self._persist_draft_cb)
        QWidget.setTabOrder(self._persist_draft_cb, self._model_input)
        QWidget.setTabOrder(self._model_input, self._model_fast_input)
        QWidget.setTabOrder(self._model_fast_input, self._save_history_cb)
        QWidget.setTabOrder(self._save_history_cb, self._exclude_sensitive_cb)
        QWidget.setTabOrder(self._exclude_sensitive_cb, self._history_limit_spin)
        QWidget.setTabOrder(self._history_limit_spin, self._auto_copy_cb)
        QWidget.setTabOrder(self._auto_copy_cb, self._global_hotkey_edit)
        QWidget.setTabOrder(self._global_hotkey_edit, self._global_collapse_hotkey_edit)
        QWidget.setTabOrder(self._global_collapse_hotkey_edit, self._collapse_shortcut_edit)
        QWidget.setTabOrder(self._collapse_shortcut_edit, self._hide_shortcut_edit)
        QWidget.setTabOrder(self._hide_shortcut_edit, self._private_shortcut_edit)
        QWidget.setTabOrder(self._private_shortcut_edit, self._startup_cb)

    def _load_from_config(self) -> None:
        cfg = load_config()
        provider = get_provider()
        idx = self._provider_combo.findData(provider)
        self._provider_combo.setCurrentIndex(idx if idx >= 0 else 0)

        if has_api_key():
            self._api_key_input.setPlaceholderText("Leave blank to keep current key")

        self._global_hotkey_edit.setKeySequence(
            QKeySequence(str(cfg.get("hotkey") or DEFAULT_HOTKEY))
        )
        self._global_collapse_hotkey_edit.setKeySequence(
            QKeySequence(str(cfg.get("hotkey_collapse") or DEFAULT_HOTKEY_COLLAPSE))
        )
        self._model_input.setText(str(cfg.get("model") or ""))
        self._model_fast_input.setText(str(cfg.get("model_fast") or ""))

        mode = str(cfg.get("mode") or "thorough").lower()
        mode_idx = self._mode_combo.findData("fast" if mode == "fast" else "thorough")
        self._mode_combo.setCurrentIndex(mode_idx if mode_idx >= 0 else 0)

        self._persist_draft_cb.setChecked(bool(cfg.get("persist_draft", True)))
        self._save_history_cb.setChecked(bool(cfg.get("save_history", True)))
        self._exclude_sensitive_cb.setChecked(bool(cfg.get("exclude_sensitive", False)))

        limit = int(cfg.get("history_limit") or 50)
        self._history_limit_spin.setValue(
            max(HISTORY_LIMIT_MIN, min(HISTORY_LIMIT_MAX, limit))
        )

        self._startup_cb.setChecked(is_start_with_windows_enabled())

        self._collapse_shortcut_edit.setKeySequence(
            QKeySequence(str(cfg.get("shortcut_collapse") or DEFAULT_SHORTCUT_COLLAPSE))
        )
        self._hide_shortcut_edit.setKeySequence(
            QKeySequence(str(cfg.get("shortcut_hide_tray") or DEFAULT_SHORTCUT_HIDE_TRAY))
        )
        self._private_shortcut_edit.setKeySequence(
            QKeySequence(str(cfg.get("shortcut_private") or DEFAULT_SHORTCUT_PRIVATE))
        )
        self._auto_copy_cb.setChecked(bool(cfg.get("auto_copy_clipboard", True)))
        self._include_project_private_cb.setChecked(
            bool(cfg.get("include_project_context_in_private", False))
        )

        if self._projects_list.count() == 0:
            self._projects_new()

    def _on_provider_changed(self, _index: int) -> None:
        if self._provider_changing:
            return
        provider = self._provider_combo.currentData()
        if not provider:
            return
        preset = PROVIDER_PRESETS[str(provider)]
        self._model_input.setText(preset["model"])
        self._model_fast_input.setText(preset["model_fast"])

    def _collect_values(self) -> dict[str, Any]:
        provider = str(self._provider_combo.currentData() or "gemini")
        mode = str(self._mode_combo.currentData() or "thorough")
        return build_settings_values(
            provider=provider,
            api_key_input=self._api_key_input.text(),
            hotkey=self._global_hotkey_edit.keySequence().toString(
                QKeySequence.SequenceFormat.PortableText
            ),
            hotkey_collapse=self._global_collapse_hotkey_edit.keySequence().toString(
                QKeySequence.SequenceFormat.PortableText
            ),
            model=self._model_input.text(),
            model_fast=self._model_fast_input.text(),
            mode=mode,
            persist_draft=self._persist_draft_cb.isChecked(),
            save_history=self._save_history_cb.isChecked(),
            exclude_sensitive=self._exclude_sensitive_cb.isChecked(),
            history_limit=self._history_limit_spin.value(),
            start_with_windows=self._startup_cb.isChecked(),
            shortcut_collapse=self._collapse_shortcut_edit.keySequence().toString(
                QKeySequence.SequenceFormat.PortableText
            ),
            shortcut_hide_tray=self._hide_shortcut_edit.keySequence().toString(
                QKeySequence.SequenceFormat.PortableText
            ),
            shortcut_private=self._private_shortcut_edit.keySequence().toString(
                QKeySequence.SequenceFormat.PortableText
            ),
            auto_copy_clipboard=self._auto_copy_cb.isChecked(),
            include_project_context_in_private=self._include_project_private_cb.isChecked(),
        )

    def _on_reset_window_position_clicked(self) -> None:
        if self._on_reset_window_position is not None:
            self._on_reset_window_position()
        self._window_reset_status.setText("Window centered on primary display.")
        self._window_reset_status.show()

    def _on_save(self) -> None:
        values = self._collect_values()
        error = apply_settings_values(values, require_api_key=self._first_run)
        if error:
            self._error.setText(error)
            self._error.show()
            return
        self._error.hide()
        if self._on_saved is not None:
            self._on_saved()
        self.accept()

    def move_to_center(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.adjustSize()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

    @staticmethod
    def run_if_needed(parent: QWidget | None = None) -> bool:
        """Show settings when no API key is configured (first-run flow)."""
        if has_api_key():
            return True
        dlg = SettingsDialog(parent, first_run=True)
        dlg.move_to_center()
        return dlg.exec() == QDialog.DialogCode.Accepted


SetupDialog = SettingsDialog
