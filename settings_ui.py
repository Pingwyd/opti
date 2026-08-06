"""
PyQt6 settings dialog for Opti configuration.
"""

from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
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
    DEFAULT_VOICE_PTT_SHORTCUT,
    PROVIDER_PRESETS,
    RESCUE_WINDOW_SHORTCUT,
    VALID_PROVIDERS,
    VALID_VOICE_MODEL_SIZES,
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
from brand import APP_NAME, SETUP_TITLE, SETTINGS_TITLE
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
        "shortcut_private": normalize_shortcut_string(
            shortcut_private, DEFAULT_SHORTCUT_PRIVATE
        ),
        "auto_copy_clipboard": auto_copy_clipboard,
        "auto_inject_enabled": auto_inject_enabled,
        "include_project_context_in_private": include_project_context_in_private,
        "voice_enabled": voice_enabled,
        "voice_transcription_mode": (
            "local" if str(voice_transcription_mode).lower() != "cloud" else "cloud"
        ),
        "voice_recording_mode": (
            "toggle"
            if str(voice_recording_mode).lower() == "toggle"
            else "push_to_talk"
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
        str(values.get("voice_ptt_shortcut") or ""),
        DEFAULT_VOICE_PTT_SHORTCUT,
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
    """Tech-stack tag editor inside a single bordered box with inline add input."""

    tags_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._box = QFrame(self)
        self._box.setObjectName("tagBox")
        box_layout = QVBoxLayout(self._box)
        box_layout.setContentsMargins(8, 8, 8, 8)
        box_layout.setSpacing(6)

        self._list = QListWidget(self._box)
        self._list.setObjectName("tagList")
        self._list.setFlow(QListWidget.Flow.LeftToRight)
        self._list.setWrapping(True)
        self._list.setFrameShape(QFrame.Shape.NoFrame)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.setMaximumHeight(120)
        box_layout.addWidget(self._list)

        self._input = QLineEdit(self._box)
        self._input.setObjectName("tagInlineInput")
        self._input.setPlaceholderText("Add technology...")
        self._input.returnPressed.connect(self._add_from_input)
        self._input.textChanged.connect(self._on_input_changed)
        box_layout.addWidget(self._input)

        layout.addWidget(self._box)

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
        chip.setObjectName("tagChipWidget")
        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(8, 3, 6, 3)
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
        item.setSizeHint(chip.sizeHint())
        if emit:
            self._refresh_tag_layout()
            self.tags_changed.emit()
        return True

    def _refresh_tag_layout(self) -> None:
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item is not None:
                widget = self._list.itemWidget(item)
                if widget is not None:
                    item.setSizeHint(widget.sizeHint())
        self._list.scheduleDelayedItemsLayout()
        self._list.updateGeometry()

    def _remove_item(self, item: QListWidgetItem) -> None:
        row = self._list.row(item)
        if row >= 0:
            self._list.takeItem(row)
            self._refresh_tag_layout()
            self.tags_changed.emit()


class ProjectListItemWidget(QFrame):
    """Single project row: name + project-type subtitle."""

    def __init__(
        self,
        *,
        name: str,
        project_type: str,
        active: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("projectListCard")
        self.setProperty("active", "true" if active else "false")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(2)

        self._name_label = QLabel(name.strip() or "Project", self)
        self._name_label.setObjectName("projectItemName")
        self._name_label.setProperty("active", "true" if active else "false")
        layout.addWidget(self._name_label)

        subtitle = (project_type or "").strip() or " "
        self._type_label = QLabel(subtitle, self)
        self._type_label.setObjectName("projectItemType")
        self._type_label.setProperty("active", "true" if active else "false")
        layout.addWidget(self._type_label)

    def set_active(self, active: bool) -> None:
        flag = "true" if active else "false"
        self.setProperty("active", flag)
        self._name_label.setProperty("active", flag)
        self._type_label.setProperty("active", flag)
        for widget in (self, self._name_label, self._type_label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def update_labels(self, *, name: str, project_type: str) -> None:
        self._name_label.setText(name.strip() or "Project")
        subtitle = (project_type or "").strip() or " "
        self._type_label.setText(subtitle)


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
        self._snapshot: dict[str, Any] = {}
        self._project_item_widgets: dict[str, ProjectListItemWidget] = {}

        self.setWindowTitle(SETUP_TITLE if first_run else SETTINGS_TITLE)
        self.setModal(True)
        self.resize(600, 640)
        self.setMinimumWidth(540)
        self.setMinimumHeight(500)

        self._build_ui()
        self.setStyleSheet(settings_stylesheet())
        self._load_from_config()
        self._snapshot = self._collect_values()
        self._connect_dirty_tracking()
        self._update_dirty_state()
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
        self._save_btn = save_btn

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
    def _section_header(text: str, parent: QWidget) -> QLabel:
        label = QLabel(text, parent)
        label.setObjectName("sectionHeader")
        return label

    @staticmethod
    def _settings_panel(parent: QWidget) -> QFrame:
        panel = QFrame(parent)
        panel.setObjectName("settingsPanel")
        return panel

    def _info_icon(self, tooltip: str, parent: QWidget) -> QLabel:
        icon = QLabel("\u2139", parent)
        icon.setObjectName("infoIcon")
        icon.setToolTip(tooltip)
        icon.setCursor(Qt.CursorShape.WhatsThisCursor)
        return icon

    def _link_button(self, text: str, parent: QWidget, *, on_click) -> QPushButton:  # noqa: ANN001
        btn = QPushButton(text, parent)
        btn.setObjectName("linkBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFlat(True)
        btn.clicked.connect(on_click)
        return btn

    def _checkbox_panel(self, checkbox: QCheckBox, parent: QWidget) -> QFrame:
        panel = self._settings_panel(parent)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(0)
        panel_layout.addWidget(checkbox)
        return panel

    def _add_section(
        self,
        layout: QVBoxLayout,
        title: str,
        parent: QWidget,
    ) -> tuple[QLabel, QFrame, QVBoxLayout]:
        header = self._section_header(title, parent)
        layout.addWidget(header)
        panel = self._settings_panel(parent)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(_FIELD_SPACING)
        layout.addWidget(panel)
        return header, panel, panel_layout

    def _shortcut_row(
        self,
        label_text: str,
        default: str,
        parent: QWidget,
        panel_layout: QVBoxLayout,
        *,
        tooltip: str | None = None,
    ) -> QKeySequenceEdit:
        row = QHBoxLayout()
        row.setSpacing(8)
        label_container = QHBoxLayout()
        label_container.setSpacing(4)
        label = QLabel(label_text, parent)
        label.setObjectName("shortcutLabel")
        label_container.addWidget(label)
        if tooltip:
            label_container.addWidget(self._info_icon(tooltip, parent))
        label_container.addStretch()
        row.addLayout(label_container, stretch=1)
        edit = QKeySequenceEdit(QKeySequence(default), parent)
        edit.setObjectName("shortcutEdit")
        edit.setFixedWidth(110)
        row.addWidget(edit)
        panel_layout.addLayout(row)
        return edit

    def _model_field(
        self,
        label_text: str,
        parent: QWidget,
        panel_layout: QVBoxLayout,
        *,
        on_reset,
    ) -> QLineEdit:
        header = QHBoxLayout()
        header.addWidget(self._field_label(label_text, parent))
        header.addStretch()
        reset_btn = self._link_button(
            "Reset to default",
            parent,
            on_click=on_reset,
        )
        header.addWidget(reset_btn)
        panel_layout.addLayout(header)
        edit = QLineEdit(parent)
        edit.setMinimumHeight(36)
        panel_layout.addWidget(edit)
        return edit

    def _build_general_tab(self) -> QWidget:
        body = self._tab_body()
        layout: QVBoxLayout = body._layout  # type: ignore[attr-defined]
        layout.addWidget(
            self._tab_description("API connection and default behavior", body)
        )

        _, _connection_panel, conn_layout = self._add_section(layout, "Connection", body)

        self._provider_combo = QComboBox(body)
        self._provider_combo.setMinimumHeight(36)
        for provider_id in VALID_PROVIDERS:
            self._provider_combo.addItem(PROVIDER_PRESETS[provider_id]["label"], provider_id)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        conn_layout.addWidget(self._field_label("Provider", body, buddy=self._provider_combo))
        conn_layout.addWidget(self._provider_combo)

        self._api_key_input = QLineEdit(body)
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText("Paste key here (leave blank to keep current)")
        self._api_key_input.setMinimumHeight(36)
        conn_layout.addWidget(self._field_label("API key", body, buddy=self._api_key_input))
        conn_layout.addWidget(self._api_key_input)

        _, _behavior_panel, behavior_layout = self._add_section(layout, "Default behavior", body)

        self._mode_combo = QComboBox(body)
        self._mode_combo.setMinimumHeight(36)
        self._mode_combo.addItem("Thorough", "thorough")
        self._mode_combo.addItem("Fast", "fast")
        behavior_layout.addWidget(
            self._field_label("Default mode", body, buddy=self._mode_combo)
        )
        behavior_layout.addWidget(self._mode_combo)

        self._persist_draft_cb = QCheckBox("Remember draft text between sessions", body)
        behavior_layout.addWidget(self._persist_draft_cb)

        _, _voice_panel, voice_layout = self._add_section(layout, "Voice input", body)

        self._voice_enabled_cb = QCheckBox("Enable voice input", body)
        voice_layout.addWidget(self._voice_enabled_cb)

        transcription_row = QHBoxLayout()
        transcription_row.setSpacing(12)
        transcription_row.addWidget(self._field_label("Transcription", body))
        self._voice_local_radio = QRadioButton("Local", body)
        self._voice_cloud_radio = QRadioButton("Cloud", body)
        self._voice_cloud_radio.setEnabled(False)
        self._voice_cloud_radio.setToolTip("Coming soon")
        self._voice_transcription_group = QButtonGroup(body)
        self._voice_transcription_group.addButton(self._voice_local_radio)
        self._voice_transcription_group.addButton(self._voice_cloud_radio)
        self._voice_local_radio.setChecked(True)
        transcription_row.addWidget(self._voice_local_radio)
        transcription_row.addWidget(self._voice_cloud_radio)
        transcription_row.addStretch()
        voice_layout.addLayout(transcription_row)

        self._voice_cloud_note = self._hint_label("Cloud transcription — coming soon.", body)
        voice_layout.addWidget(self._voice_cloud_note)

        self._voice_private_note = self._hint_label(
            "Private mode requires local transcription.", body
        )
        voice_layout.addWidget(self._voice_private_note)

        recording_row = QHBoxLayout()
        recording_row.setSpacing(12)
        recording_row.addWidget(self._field_label("Recording mode", body))
        self._voice_ptt_radio = QRadioButton("Push-to-talk", body)
        self._voice_toggle_radio = QRadioButton("Toggle", body)
        self._voice_recording_group = QButtonGroup(body)
        self._voice_recording_group.addButton(self._voice_ptt_radio)
        self._voice_recording_group.addButton(self._voice_toggle_radio)
        self._voice_ptt_radio.setChecked(True)
        recording_row.addWidget(self._voice_ptt_radio)
        recording_row.addWidget(self._voice_toggle_radio)
        recording_row.addStretch()
        voice_layout.addLayout(recording_row)

        model_row = QHBoxLayout()
        self._voice_model_combo = QComboBox(body)
        self._voice_model_combo.setMinimumHeight(36)
        self._voice_model_combo.setFixedWidth(140)
        for size in VALID_VOICE_MODEL_SIZES:
            self._voice_model_combo.addItem(size, size)
        model_row.addWidget(self._field_label("Local model size", body, buddy=self._voice_model_combo))
        model_row.addStretch()
        model_row.addWidget(self._voice_model_combo)
        voice_layout.addLayout(model_row)

        toggle_max_row = QHBoxLayout()
        self._voice_toggle_max_spin = QSpinBox(body)
        self._voice_toggle_max_spin.setRange(5, 600)
        self._voice_toggle_max_spin.setSuffix(" s")
        self._voice_toggle_max_spin.setMinimumHeight(36)
        self._voice_toggle_max_spin.setFixedWidth(90)
        toggle_max_row.addWidget(
            self._field_label("Max toggle recording duration", body, buddy=self._voice_toggle_max_spin)
        )
        toggle_max_row.addStretch()
        toggle_max_row.addWidget(self._voice_toggle_max_spin)
        voice_layout.addLayout(toggle_max_row)

        self._voice_ptt_shortcut_edit = self._shortcut_row(
            "Push-to-talk shortcut (popup focused)",
            DEFAULT_VOICE_PTT_SHORTCUT,
            body,
            voice_layout,
            tooltip=(
                "Hold this key while the pill is focused to record. "
                f"Not global — works only when {APP_NAME} is focused."
            ),
        )

        if not self._first_run:
            _, _window_panel, window_layout = self._add_section(layout, "Window position", body)
            reset_btn = QPushButton("Reset window position", body)
            reset_btn.setObjectName("cancelBtn")
            reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            reset_btn.setMinimumHeight(36)
            reset_btn.clicked.connect(self._on_reset_window_position_clicked)
            window_layout.addWidget(reset_btn)
            self._window_reset_status = QLabel("", body)
            self._window_reset_status.setObjectName("fieldHint")
            self._window_reset_status.hide()
            window_layout.addWidget(self._window_reset_status)
        else:
            self._window_reset_status = QLabel("", body)
            self._window_reset_status.hide()

        layout.addStretch()
        return self._scroll_tab(body)

    def _build_models_tab(self) -> QWidget:
        body = self._tab_body()
        layout: QVBoxLayout = body._layout  # type: ignore[attr-defined]
        layout.addWidget(self._tab_description("LLM model IDs per provider", body))

        models_panel = self._settings_panel(body)
        models_layout = QVBoxLayout(models_panel)
        models_layout.setContentsMargins(12, 12, 12, 12)
        models_layout.setSpacing(_FIELD_SPACING)

        self._model_input = self._model_field(
            "Thorough model",
            body,
            models_layout,
            on_reset=lambda: self._reset_model_field("model"),
        )
        self._model_fast_input = self._model_field(
            "Fast model",
            body,
            models_layout,
            on_reset=lambda: self._reset_model_field("model_fast"),
        )

        hint_row = QHBoxLayout()
        hint_row.setSpacing(4)
        hint_row.addWidget(
            self._info_icon(
                "Changing provider resets these to that provider's defaults.",
                body,
            )
        )
        hint_row.addStretch()
        models_layout.addLayout(hint_row)
        layout.addWidget(models_panel)

        layout.addStretch()
        return self._scroll_tab(body)

    def _build_privacy_tab(self) -> QWidget:
        body = self._tab_body()
        layout: QVBoxLayout = body._layout  # type: ignore[attr-defined]
        layout.addWidget(self._tab_description("History and clipboard", body))

        _, _history_panel, history_layout = self._add_section(layout, "History", body)

        self._save_history_cb = QCheckBox("Save optimization history", body)
        history_layout.addWidget(self._save_history_cb)

        self._exclude_sensitive_cb = QCheckBox(
            "Don't save prompts containing sensitive patterns", body
        )
        history_layout.addWidget(self._exclude_sensitive_cb)

        limit_row = QHBoxLayout()
        self._history_limit_spin = QSpinBox(body)
        self._history_limit_spin.setRange(HISTORY_LIMIT_MIN, HISTORY_LIMIT_MAX)
        self._history_limit_spin.setSingleStep(50)
        self._history_limit_spin.setMinimumHeight(36)
        self._history_limit_spin.setFixedWidth(70)
        limit_row.addWidget(
            self._field_label("History limit", body, buddy=self._history_limit_spin)
        )
        limit_row.addStretch()
        limit_row.addWidget(self._history_limit_spin)
        history_layout.addLayout(limit_row)

        _, _clipboard_panel, clipboard_layout = self._add_section(layout, "Clipboard", body)

        self._auto_copy_cb = QCheckBox("Auto-copy optimized output", body)
        clipboard_layout.addWidget(self._auto_copy_cb)

        self._auto_inject_cb = QCheckBox(
            "Enable Auto-Inject (paste into the field you were using)", body
        )
        clipboard_layout.addWidget(self._auto_inject_cb)
        clipboard_layout.addWidget(
            self._hint_label(
                "Auto-Inject simulates a paste into your previously active window. "
                "It never injects without your confirmation.",
                body,
            )
        )

        _, _project_panel, project_privacy_layout = self._add_section(
            layout, "Project context", body
        )

        self._include_project_private_cb = QCheckBox(
            "Include project context in private mode", body
        )
        project_privacy_layout.addWidget(self._include_project_private_cb)

        layout.addStretch()
        return self._scroll_tab(body)

    def _build_shortcuts_tab(self) -> QWidget:
        body = self._tab_body()
        layout: QVBoxLayout = body._layout  # type: ignore[attr-defined]
        layout.addWidget(
            self._tab_description("Global and in-app keyboard shortcuts", body)
        )

        _, _global_panel, global_layout = self._add_section(layout, "Global", body)

        self._global_hotkey_edit = self._shortcut_row(
            f"Open / hide {APP_NAME}",
            DEFAULT_HOTKEY,
            body,
            global_layout,
            tooltip=(
                "Works system-wide. Open hotkey toggles show/hide (expanded or chip). "
                "On macOS, grant Accessibility to this app."
            ),
        )
        self._global_collapse_hotkey_edit = self._shortcut_row(
            "Collapse to chip",
            DEFAULT_HOTKEY_COLLAPSE,
            body,
            global_layout,
            tooltip=(
                "Works system-wide. Collapse hotkey toggles chip ↔ expanded; "
                "when hidden, shows as chip."
            ),
        )

        _, _popup_panel, popup_layout = self._add_section(
            layout, "When popup is focused", body
        )

        self._collapse_shortcut_edit = self._shortcut_row(
            "Collapse to chip",
            DEFAULT_SHORTCUT_COLLAPSE,
            body,
            popup_layout,
        )
        self._hide_shortcut_edit = self._shortcut_row(
            "Hide to tray",
            DEFAULT_SHORTCUT_HIDE_TRAY,
            body,
            popup_layout,
        )
        self._private_shortcut_edit = self._shortcut_row(
            "Toggle private session",
            DEFAULT_SHORTCUT_PRIVATE,
            body,
            popup_layout,
            tooltip=f"Rescue off-screen windows with {RESCUE_WINDOW_SHORTCUT} (not configurable).",
        )

        layout.addStretch()
        return self._scroll_tab(body)

    def _build_startup_tab(self) -> QWidget:
        body = self._tab_body()
        layout: QVBoxLayout = body._layout  # type: ignore[attr-defined]
        layout.addWidget(self._tab_description("Launch options", body))

        self._startup_cb = QCheckBox(f"Start {APP_NAME} with Windows", body)
        layout.addWidget(self._checkbox_panel(self._startup_cb, body))

        self._start_minimized_cb = QCheckBox("Start minimized to tray", body)
        layout.addWidget(self._checkbox_panel(self._start_minimized_cb, body))

        self._check_updates_cb = QCheckBox("Check for updates on launch", body)
        layout.addWidget(self._checkbox_panel(self._check_updates_cb, body))

        layout.addStretch()
        return self._scroll_tab(body)

    def _build_projects_tab(self) -> QWidget:
        body = self._tab_body()
        layout: QVBoxLayout = body._layout  # type: ignore[attr-defined]
        layout.addWidget(
            self._tab_description("Reusable context for optimizations", body)
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(0)

        list_panel = QWidget(body)
        list_panel.setFixedWidth(180)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)

        new_btn = QPushButton("+ New project", list_panel)
        new_btn.setObjectName("saveBtn")
        new_btn.setProperty("dirty", "true")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._projects_new)
        list_layout.addWidget(new_btn)

        self._projects_list = QListWidget(list_panel)
        self._projects_list.setObjectName("projectsList")
        self._projects_list.currentItemChanged.connect(self._on_project_selected)
        list_layout.addWidget(self._projects_list, stretch=1)

        form_panel = QWidget(body)
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(_FIELD_SPACING)

        self._project_name_input = QLineEdit(form_panel)
        self._project_name_input.setMinimumHeight(36)
        self._project_name_input.textChanged.connect(self._sync_project_list_preview)
        form_layout.addWidget(
            self._field_label("Name", form_panel, buddy=self._project_name_input)
        )
        form_layout.addWidget(self._project_name_input)

        self._project_tags = TagInputWidget(form_panel)
        self._project_tags.tags_changed.connect(self._sync_project_list_preview)
        form_layout.addWidget(self._field_label("Tech stack", form_panel))
        form_layout.addWidget(self._project_tags)

        self._project_type_combo = QComboBox(form_panel)
        self._project_type_combo.setMinimumHeight(36)
        self._project_type_combo.addItem("(none)", "")
        for ptype in PROJECT_TYPES:
            if ptype:
                self._project_type_combo.addItem(ptype, ptype)
        self._project_type_combo.currentIndexChanged.connect(self._sync_project_list_preview)
        form_layout.addWidget(
            self._field_label("Project type", form_panel, buddy=self._project_type_combo)
        )
        form_layout.addWidget(self._project_type_combo)

        self._project_conventions = QTextEdit(form_panel)
        self._project_conventions.setPlaceholderText("How this project does things...")
        self._project_conventions.setMinimumHeight(72)
        form_layout.addWidget(self._field_label("Conventions", form_panel))
        form_layout.addWidget(self._project_conventions)

        self._project_notes = QTextEdit(form_panel)
        self._project_notes.setPlaceholderText("Additional notes…")
        self._project_notes.setMinimumHeight(72)
        form_layout.addWidget(self._field_label("Notes", form_panel))
        form_layout.addWidget(self._project_notes)

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
        save_project_btn.setProperty("dirty", "true")
        save_project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_project_btn.clicked.connect(self._projects_save)
        btn_row.addWidget(save_project_btn)
        form_layout.addLayout(btn_row)
        form_layout.addStretch()

        grid.addWidget(list_panel, 0, 0)
        grid.addWidget(form_panel, 0, 1)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self._reload_projects_list()
        return self._scroll_tab(body)

    def _project_type_label(self, project_type: str) -> str:
        return (project_type or "").strip()

    def _sync_project_list_preview(self) -> None:
        current = self._projects_list.currentItem()
        if current is None:
            return
        project_id = str(current.data(Qt.ItemDataRole.UserRole) or "")
        widget = self._project_item_widgets.get(project_id)
        if widget is None:
            return
        widget.update_labels(
            name=self._project_name_input.text(),
            project_type=str(self._project_type_combo.currentText() or ""),
        )

    def _update_project_list_selection_styles(self) -> None:
        current = self._projects_list.currentItem()
        current_id = str(current.data(Qt.ItemDataRole.UserRole) or "") if current else ""
        for project_id, widget in self._project_item_widgets.items():
            widget.set_active(project_id == current_id)

    def _reload_projects_list(self, *, select_id: str | None = None) -> None:
        self._projects_list.blockSignals(True)
        self._projects_list.clear()
        self._project_item_widgets.clear()
        for project in list_projects():
            project_id = str(project.get("id"))
            widget = ProjectListItemWidget(
                name=str(project.get("name") or project.get("id") or "Project"),
                project_type=self._project_type_label(str(project.get("project_type") or "")),
                parent=self._projects_list,
            )
            self._project_item_widgets[project_id] = widget
            item = QListWidgetItem(self._projects_list)
            item.setData(Qt.ItemDataRole.UserRole, project_id)
            item.setSizeHint(widget.sizeHint())
            self._projects_list.addItem(item)
            self._projects_list.setItemWidget(item, widget)
            if select_id and project_id == select_id:
                self._projects_list.setCurrentItem(item)
        self._projects_list.blockSignals(False)
        if select_id is None and self._projects_list.count() > 0:
            self._projects_list.setCurrentRow(0)
        self._update_project_list_selection_styles()

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
        self._update_project_list_selection_styles()
        if current is None:
            return
        project_id = str(current.data(Qt.ItemDataRole.UserRole) or "")
        if project_id:
            self._load_project_form(project_id)

    def _projects_new(self) -> None:
        self._selected_project_id = None
        self._projects_is_new = True
        self._projects_list.clearSelection()
        self._update_project_list_selection_styles()
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
        QWidget.setTabOrder(self._persist_draft_cb, self._voice_enabled_cb)
        QWidget.setTabOrder(self._voice_enabled_cb, self._voice_local_radio)
        QWidget.setTabOrder(self._voice_local_radio, self._voice_cloud_radio)
        QWidget.setTabOrder(self._voice_cloud_radio, self._voice_ptt_radio)
        QWidget.setTabOrder(self._voice_ptt_radio, self._voice_toggle_radio)
        QWidget.setTabOrder(self._voice_toggle_radio, self._voice_model_combo)
        QWidget.setTabOrder(self._voice_model_combo, self._voice_toggle_max_spin)
        QWidget.setTabOrder(self._voice_toggle_max_spin, self._voice_ptt_shortcut_edit)
        QWidget.setTabOrder(self._voice_ptt_shortcut_edit, self._model_input)
        QWidget.setTabOrder(self._model_input, self._model_fast_input)
        QWidget.setTabOrder(self._model_fast_input, self._save_history_cb)
        QWidget.setTabOrder(self._save_history_cb, self._exclude_sensitive_cb)
        QWidget.setTabOrder(self._exclude_sensitive_cb, self._history_limit_spin)
        QWidget.setTabOrder(self._history_limit_spin, self._auto_copy_cb)
        QWidget.setTabOrder(self._auto_copy_cb, self._auto_inject_cb)
        QWidget.setTabOrder(self._auto_inject_cb, self._global_hotkey_edit)
        QWidget.setTabOrder(self._global_hotkey_edit, self._global_collapse_hotkey_edit)
        QWidget.setTabOrder(self._global_collapse_hotkey_edit, self._collapse_shortcut_edit)
        QWidget.setTabOrder(self._collapse_shortcut_edit, self._hide_shortcut_edit)
        QWidget.setTabOrder(self._hide_shortcut_edit, self._private_shortcut_edit)
        QWidget.setTabOrder(self._private_shortcut_edit, self._startup_cb)
        QWidget.setTabOrder(self._startup_cb, self._start_minimized_cb)
        QWidget.setTabOrder(self._start_minimized_cb, self._check_updates_cb)

    def _reset_model_field(self, field: str) -> None:
        provider = str(self._provider_combo.currentData() or "gemini")
        preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["gemini"])
        if field == "model":
            self._model_input.setText(str(preset["model"]))
        else:
            self._model_fast_input.setText(str(preset["model_fast"]))
        self._update_dirty_state()

    def _connect_dirty_tracking(self) -> None:
        widgets: list[QWidget] = [
            self._provider_combo,
            self._api_key_input,
            self._mode_combo,
            self._persist_draft_cb,
            self._model_input,
            self._model_fast_input,
            self._save_history_cb,
            self._exclude_sensitive_cb,
            self._history_limit_spin,
            self._auto_copy_cb,
            self._auto_inject_cb,
            self._include_project_private_cb,
            self._global_hotkey_edit,
            self._global_collapse_hotkey_edit,
            self._collapse_shortcut_edit,
            self._hide_shortcut_edit,
            self._private_shortcut_edit,
            self._startup_cb,
            self._start_minimized_cb,
            self._check_updates_cb,
            self._voice_enabled_cb,
            self._voice_local_radio,
            self._voice_cloud_radio,
            self._voice_ptt_radio,
            self._voice_toggle_radio,
            self._voice_model_combo,
            self._voice_toggle_max_spin,
            self._voice_ptt_shortcut_edit,
        ]
        for widget in widgets:
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._update_dirty_state)
            elif isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._update_dirty_state)
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(self._update_dirty_state)
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self._update_dirty_state)
            elif isinstance(widget, QKeySequenceEdit):
                widget.keySequenceChanged.connect(self._update_dirty_state)
            elif isinstance(widget, QRadioButton):
                widget.toggled.connect(self._update_dirty_state)

    def _update_dirty_state(self) -> None:
        dirty = self._first_run or self._collect_values() != self._snapshot
        self._save_btn.setProperty("dirty", "true" if dirty else "false")
        self._save_btn.style().unpolish(self._save_btn)
        self._save_btn.style().polish(self._save_btn)

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
        self._start_minimized_cb.setChecked(bool(cfg.get("start_minimized_to_tray", True)))
        self._check_updates_cb.setChecked(bool(cfg.get("check_updates_on_launch", False)))

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
        self._auto_inject_cb.setChecked(bool(cfg.get("auto_inject_enabled", False)))
        self._include_project_private_cb.setChecked(
            bool(cfg.get("include_project_context_in_private", False))
        )

        self._voice_enabled_cb.setChecked(bool(cfg.get("voice_enabled", False)))
        transcription_mode = str(cfg.get("voice_transcription_mode") or "local").lower()
        self._voice_local_radio.setChecked(transcription_mode != "cloud")
        self._voice_cloud_radio.setChecked(transcription_mode == "cloud")

        recording_mode = str(cfg.get("voice_recording_mode") or "push_to_talk").lower()
        self._voice_ptt_radio.setChecked(recording_mode != "toggle")
        self._voice_toggle_radio.setChecked(recording_mode == "toggle")

        model_size = str(cfg.get("voice_model_size") or "base").lower()
        model_idx = self._voice_model_combo.findData(model_size)
        self._voice_model_combo.setCurrentIndex(model_idx if model_idx >= 0 else 1)

        self._voice_toggle_max_spin.setValue(int(cfg.get("voice_toggle_max_seconds") or 60))
        self._voice_ptt_shortcut_edit.setKeySequence(
            QKeySequence(str(cfg.get("voice_ptt_shortcut") or DEFAULT_VOICE_PTT_SHORTCUT))
        )
        self._update_voice_cloud_state()

        if self._projects_list.count() == 0:
            self._projects_new()

    def _update_voice_cloud_state(self) -> None:
        self._voice_cloud_radio.setEnabled(False)
        self._voice_cloud_note.show()

    def _on_provider_changed(self, _index: int) -> None:
        if self._provider_changing:
            return
        provider = self._provider_combo.currentData()
        if not provider:
            return
        preset = PROVIDER_PRESETS[str(provider)]
        self._model_input.setText(preset["model"])
        self._model_fast_input.setText(preset["model_fast"])
        self._update_dirty_state()

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
            start_minimized_to_tray=self._start_minimized_cb.isChecked(),
            check_updates_on_launch=self._check_updates_cb.isChecked(),
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
            auto_inject_enabled=self._auto_inject_cb.isChecked(),
            include_project_context_in_private=self._include_project_private_cb.isChecked(),
            voice_enabled=self._voice_enabled_cb.isChecked(),
            voice_transcription_mode=(
                "cloud" if self._voice_cloud_radio.isChecked() else "local"
            ),
            voice_recording_mode=(
                "toggle" if self._voice_toggle_radio.isChecked() else "push_to_talk"
            ),
            voice_model_size=str(self._voice_model_combo.currentData() or "base"),
            voice_toggle_max_seconds=self._voice_toggle_max_spin.value(),
            voice_ptt_shortcut=self._voice_ptt_shortcut_edit.keySequence().toString(
                QKeySequence.SequenceFormat.PortableText
            ),
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
