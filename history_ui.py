"""
PyQt6 history browser dialog: search, paginate, and reuse past optimizations.
"""

from __future__ import annotations

import shutil
from datetime import date, datetime, timedelta, timezone
from typing import Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from history import distinct_project_names, history_file_path, query_entries
from config import get_hotkey
from settings_ui import SettingsDialog
from ui_theme import DESIGN_TOKENS, history_stylesheet

_C = DESIGN_TOKENS["color"]

PAGE_SIZE = 25
SEARCH_DEBOUNCE_MS = 300

_DATE_RANGE_OPTIONS = (
    ("All", None),
    ("7d", 7),
    ("30d", 30),
    ("90d", 90),
)

_PROJECT_TAG_COLORS: tuple[tuple[str, str, str], ...] = (
    ("rgba(99, 102, 241, 0.18)", "rgba(99, 102, 241, 0.42)", "#a5b4fc"),
    ("rgba(34, 197, 94, 0.15)", "rgba(34, 197, 94, 0.38)", "#86efac"),
    ("rgba(56, 189, 248, 0.15)", "rgba(56, 189, 248, 0.38)", "#7dd3fc"),
    ("rgba(251, 191, 36, 0.15)", "rgba(251, 191, 36, 0.38)", "#fcd34d"),
    ("rgba(244, 114, 182, 0.15)", "rgba(244, 114, 182, 0.38)", "#f9a8d4"),
    ("rgba(167, 139, 250, 0.15)", "rgba(167, 139, 250, 0.38)", "#c4b5fd"),
)


def _format_timestamp(ts: str) -> str:
    parsed = None
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return ts
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone()
    return local.strftime("%Y-%m-%d %H:%M")


def _project_tag_colors(name: str) -> tuple[str, str, str]:
    idx = sum(ord(c) for c in name.lower()) % len(_PROJECT_TAG_COLORS)
    return _PROJECT_TAG_COLORS[idx]


def _project_tag_stylesheet(name: str | None, *, selected: bool = False) -> str:
    base = (
        "border-radius: 10px; padding: 2px 8px; font-size: 11px; font-weight: 600;"
    )
    if not name:
        if selected:
            return (
                f"{base} background: rgba(255, 255, 255, 0.10);"
                f" color: {_C['text_muted']};"
                f" border: 1px solid {_C['accent_border']};"
            )
        return (
            f"{base} background: rgba(255, 255, 255, 0.04);"
            f" color: {_C['text_muted']};"
            f" border: 1px solid {_C['border_subtle']};"
        )
    if selected:
        return (
            f"{base} background: {_C['accent']};"
            f" color: #1a1a1a;"
            f" border: 1px solid {_C['accent']};"
        )
    bg, border, text = _project_tag_colors(name)
    return f"{base} background: {bg}; color: {text}; border: 1px solid {border};"


class _ProjectModelCell(QWidget):
    """Stacked project tag pill and model name for a history table row."""

    def __init__(
        self,
        project_name: str | None,
        model: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("projectModelCell")
        self._project_name = (project_name or "").strip() or None
        self._selected = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)

        self._tag = QLabel(self._project_name or "No project", self)
        self._tag.setObjectName("projectTag")
        self._tag.setSizePolicy(
            self._tag.sizePolicy().horizontalPolicy(),
            self._tag.sizePolicy().verticalPolicy(),
        )
        self._tag.setMaximumHeight(22)

        self._model = QLabel(model or "—", self)
        self._model.setObjectName("modelName")

        layout.addWidget(self._tag, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._model, alignment=Qt.AlignmentFlag.AlignLeft)
        self._apply_styles()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._apply_styles()

    def _apply_styles(self) -> None:
        self._tag.setStyleSheet(_project_tag_stylesheet(self._project_name, selected=self._selected))
        row_bg = "rgba(240, 128, 96, 0.14)" if self._selected else "transparent"
        self.setStyleSheet(f"background: {row_bg};")


class _StatusIconCell(QWidget):
    """Small green checkmark indicating a completed optimization."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusIconCell")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(0)
        icon = QLabel("✓", self)
        icon.setObjectName("statusCheck")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setAccessibleName("Optimized")
        layout.addStretch()
        layout.addWidget(icon)

    def set_selected(self, selected: bool) -> None:
        row_bg = "rgba(240, 128, 96, 0.14)" if selected else "transparent"
        self.setStyleSheet(f"background: {row_bg};")


class _FilterChip(QPushButton):
    """Dismissible chip representing an active search or date filter."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.setObjectName("filterChip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"Remove filter: {label}")


class HistoryDialog(QDialog):
    """Searchable, paginated view of local optimization history."""

    use_prompt_requested = pyqtSignal(str)
    use_both_requested = pyqtSignal(str, str)
    rerun_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Optimization history")
        self.resize(960, 640)
        self._current_offset = 0
        self._total_count = 0
        self._loaded_entries: list[dict[str, Any]] = []
        self._selected_entry: dict[str, Any] | None = None
        self._date_pill_buttons: list[QPushButton] = []
        self._project_filter: str | None = None
        self._highlighted_row = -1

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._reload_from_start)

        self._build_ui()
        self._apply_styles()
        self._reload_from_start()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(12)

        # --- Header ---
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel("History", self)
        title.setObjectName("historyTitle")
        title.setAccessibleName("History")
        title_block.addWidget(title)
        self._header_count = QLabel("", self)
        self._header_count.setObjectName("historySubtitle")
        self._header_count.setAccessibleName("History entry count")
        title_block.addWidget(self._header_count)
        header_row.addLayout(title_block)
        header_row.addStretch()

        export_btn = QPushButton("Export", self)
        export_btn.setObjectName("headerBtn")
        export_btn.setAccessibleName("Export history JSON")
        export_btn.clicked.connect(self._export_json)
        header_row.addWidget(export_btn)

        settings_btn = QPushButton("⚙", self)
        settings_btn.setObjectName("headerBtn")
        settings_btn.setAccessibleName("Open settings")
        settings_btn.setToolTip("Settings")
        settings_btn.setFixedSize(36, 32)
        settings_btn.clicked.connect(self._open_settings)
        header_row.addWidget(settings_btn)

        close_btn = QPushButton("×", self)
        close_btn.setObjectName("closeBtn")
        close_btn.setAccessibleName("Close history")
        close_btn.setFixedSize(32, 32)
        close_btn.clicked.connect(self.accept)
        header_row.addWidget(close_btn)

        root.addLayout(header_row)

        # --- Search bar ---
        search_wrap = QFrame(self)
        search_wrap.setObjectName("searchBar")
        search_layout = QHBoxLayout(search_wrap)
        search_layout.setContentsMargins(12, 0, 12, 0)
        search_layout.setSpacing(8)

        search_icon = QLabel("⌕", search_wrap)
        search_icon.setObjectName("searchIcon")
        search_icon.setAccessibleName("Search icon")
        search_layout.addWidget(search_icon)

        self._search = QLineEdit(search_wrap)
        self._search.setObjectName("historySearch")
        self._search.setPlaceholderText("Search prompts and results…")
        self._search.setAccessibleName("History search")
        self._search.setFrame(False)
        self._search.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search, stretch=1)

        root.addWidget(search_wrap)

        # --- Filters: date pills + project dropdown in one bar ---
        filters_frame = QFrame(self)
        filters_frame.setObjectName("filtersBar")
        filters_layout = QHBoxLayout(filters_frame)
        filters_layout.setContentsMargins(12, 8, 12, 8)
        filters_layout.setSpacing(8)

        self._date_group = QButtonGroup(self)
        self._date_group.setExclusive(True)
        for index, (label, _days) in enumerate(_DATE_RANGE_OPTIONS):
            btn = QPushButton(label, self)
            btn.setObjectName("filterPill")
            btn.setCheckable(True)
            btn.setAccessibleName(f"Filter: {label}")
            if index == 0:
                btn.setChecked(True)
            self._date_group.addButton(btn, index)
            self._date_pill_buttons.append(btn)
            filters_layout.addWidget(btn)
        self._date_group.idClicked.connect(self._on_date_pill_clicked)

        separator = QFrame(filters_frame)
        separator.setObjectName("filterSeparator")
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFixedWidth(1)
        filters_layout.addWidget(separator)

        self._project_combo = QComboBox(filters_frame)
        self._project_combo.setObjectName("historyProjectFilter")
        self._project_combo.setMinimumHeight(32)
        self._project_combo.setMinimumWidth(160)
        self._project_combo.currentIndexChanged.connect(self._on_project_filter_changed)
        filters_layout.addWidget(self._project_combo, stretch=1)

        root.addWidget(filters_frame)

        self._reload_project_filter_options()

        # --- Search filter chip (optional, when keyword active) ---
        self._chips_row = QWidget(self)
        self._chips_row.setObjectName("chipsRow")
        self._chips_layout = QHBoxLayout(self._chips_row)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(6)
        self._chips_layout.addStretch()
        self._chips_row.hide()
        root.addWidget(self._chips_row)

        # --- List + detail splitter ---
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("historySplitter")

        table_wrap = QWidget(splitter)
        table_layout = QVBoxLayout(table_wrap)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        self._table_stack = QStackedWidget(table_wrap)
        self._table = QTableWidget(0, 3)
        self._table.setObjectName("historyTable")
        self._table.setHorizontalHeaderLabels(["Time", "Project / model", ""])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAccessibleName("History entries")
        self._table.setSortingEnabled(True)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSortIndicatorShown(True)
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._on_header_clicked)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.cellDoubleClicked.connect(lambda _r, _c: self._focus_detail())
        self._table.verticalHeader().setDefaultSectionSize(52)
        self._table_stack.addWidget(self._table)

        self._empty_state = QLabel("No matching history entries")
        self._empty_state.setObjectName("historyEmptyState")
        self._empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_state.setWordWrap(True)
        self._empty_state.setAccessibleName("No history results")
        self._table_stack.addWidget(self._empty_state)
        table_layout.addWidget(self._table_stack)

        detail_card = QFrame(splitter)
        detail_card.setObjectName("historyDetailCard")
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(6)

        input_label = QLabel("Original prompt", detail_card)
        input_label.setObjectName("detailLabel")
        detail_layout.addWidget(input_label)
        self._input_detail = QTextEdit(detail_card)
        self._input_detail.setObjectName("detailInput")
        self._input_detail.setReadOnly(True)
        self._input_detail.setAccessibleName("History entry input")
        detail_layout.addWidget(self._input_detail, stretch=1)

        output_label = QLabel("Optimized result", detail_card)
        output_label.setObjectName("detailLabel")
        detail_layout.addWidget(output_label)
        self._output_detail = QTextEdit(detail_card)
        self._output_detail.setObjectName("detailOutput")
        self._output_detail.setReadOnly(True)
        self._output_detail.setAccessibleName("History entry output")
        detail_layout.addWidget(self._output_detail, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._use_prompt_btn = QPushButton("Use prompt", detail_card)
        self._use_prompt_btn.setObjectName("detailBtnPrimary")
        self._use_prompt_btn.setAccessibleName("Use prompt")
        self._use_prompt_btn.clicked.connect(self._emit_use_prompt)
        btn_row.addWidget(self._use_prompt_btn)

        self._use_both_btn = QPushButton("Use both", detail_card)
        self._use_both_btn.setObjectName("detailBtnGhost")
        self._use_both_btn.setAccessibleName("Use both prompt and result")
        self._use_both_btn.clicked.connect(self._emit_use_both)
        btn_row.addWidget(self._use_both_btn)

        self._rerun_btn = QPushButton("↻", detail_card)
        self._rerun_btn.setObjectName("detailBtnIcon")
        self._rerun_btn.setAccessibleName("Re-run optimization")
        self._rerun_btn.setToolTip("Re-run optimization")
        self._rerun_btn.setFixedSize(36, 36)
        self._rerun_btn.clicked.connect(self._emit_rerun)
        btn_row.addWidget(self._rerun_btn)

        btn_row.addStretch()
        detail_layout.addLayout(btn_row)

        splitter.addWidget(table_wrap)
        splitter.addWidget(detail_card)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        root.addWidget(splitter, stretch=1)

        # --- Pagination ---
        page_row = QHBoxLayout()
        page_row.setSpacing(10)

        self._page_info = QLabel("", self)
        self._page_info.setObjectName("pageInfo")
        self._page_info.setAccessibleName("Pagination info")
        page_row.addWidget(self._page_info)

        page_row.addStretch()

        self._prev_btn = QPushButton("◀ Prev", self)
        self._prev_btn.setObjectName("pageBtn")
        self._prev_btn.setAccessibleName("Previous page")
        self._prev_btn.clicked.connect(self._prev_page)
        page_row.addWidget(self._prev_btn)

        self._next_btn = QPushButton("Next ▶", self)
        self._next_btn.setObjectName("pageBtn")
        self._next_btn.setAccessibleName("Next page")
        self._next_btn.clicked.connect(self._next_page)
        page_row.addWidget(self._next_btn)

        root.addLayout(page_row)

        self._set_detail_enabled(False)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self)
        dlg.exec()

    def _apply_styles(self) -> None:
        self.setStyleSheet(history_stylesheet())

    def _reload_project_filter_options(self) -> None:
        current = self._project_filter
        self._project_combo.blockSignals(True)
        self._project_combo.clear()
        self._project_combo.addItem("All projects", "")
        for name in distinct_project_names():
            self._project_combo.addItem(name, name)
        if current:
            idx = self._project_combo.findData(current)
            self._project_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self._project_combo.setCurrentIndex(0)
        self._project_combo.blockSignals(False)

    def _on_project_filter_changed(self, _index: int) -> None:
        value = str(self._project_combo.currentData() or "").strip()
        self._project_filter = value or None
        self._reload_from_start()

    def _selected_date_index(self) -> int:
        return self._date_group.checkedId()

    def _date_range_for_index(self, index: int) -> tuple[date | None, date | None]:
        days = _DATE_RANGE_OPTIONS[index][1]
        if days is None:
            return None, None
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=days - 1)
        return start, today

    def _date_range(self) -> tuple[date | None, date | None]:
        return self._date_range_for_index(self._selected_date_index())

    def _on_date_pill_clicked(self, _index: int) -> None:
        self._reload_from_start()

    def _on_search_changed(self, _text: str) -> None:
        self._search_timer.start(SEARCH_DEBOUNCE_MS)

    def _query_total(self, date_index: int, keyword: str | None = None) -> int:
        date_from, date_to = self._date_range_for_index(date_index)
        _entries, total = query_entries(
            keyword=keyword,
            date_from=date_from,
            date_to=date_to,
            project=self._project_filter,
            offset=0,
            limit=1,
        )
        return total

    def _update_pill_counts(self) -> None:
        keyword = self._search.text().strip() or None
        for index, btn in enumerate(self._date_pill_buttons):
            label = _DATE_RANGE_OPTIONS[index][0]
            count = self._query_total(index, keyword=keyword)
            btn.setText(f"{label}  {count}")

    def _update_filter_chips(self) -> None:
        while self._chips_layout.count() > 1:
            item = self._chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        keyword = self._search.text().strip()
        if keyword:
            chip = _FilterChip(f'Search: "{keyword}"  ×', self._chips_row)
            chip.clicked.connect(self._clear_search)
            self._chips_layout.insertWidget(0, chip)
            self._chips_row.setVisible(True)
        else:
            self._chips_row.setVisible(False)

    def _clear_search(self) -> None:
        self._search.blockSignals(True)
        self._search.clear()
        self._search.blockSignals(False)
        self._reload_from_start()

    def _reload_from_start(self) -> None:
        self._current_offset = 0
        self._load_page()

    def _load_page(self) -> None:
        date_from, date_to = self._date_range()
        keyword = self._search.text().strip() or None
        entries, total = query_entries(
            keyword=keyword,
            date_from=date_from,
            date_to=date_to,
            project=self._project_filter,
            offset=self._current_offset,
            limit=PAGE_SIZE,
        )
        self._loaded_entries = entries
        self._total_count = total
        self._populate_table(entries)
        self._update_pagination()
        self._update_header_count()
        self._update_pill_counts()
        self._update_filter_chips()
        self._update_empty_state()
        self._reload_project_filter_options()

        if entries:
            self._table.selectRow(0)
            self._set_row_highlight(0, True)
            self._highlighted_row = 0
        else:
            self._selected_entry = None
            self._input_detail.clear()
            self._output_detail.clear()
            self._set_detail_enabled(False)

    def _has_active_filters(self) -> bool:
        keyword = self._search.text().strip()
        date_index = self._selected_date_index()
        return bool(keyword) or date_index > 0 or bool(self._project_filter)

    def _update_empty_state(self) -> None:
        if self._total_count:
            self._table_stack.setCurrentIndex(0)
            return
        self._table_stack.setCurrentIndex(1)
        if self._has_active_filters():
            self._empty_state.setText("No matching history entries")
        else:
            hotkey = get_hotkey()
            self._empty_state.setText(
                f"No optimizations yet\n\nPress {hotkey} to optimize a prompt."
            )

    def _update_header_count(self) -> None:
        if self._total_count == 1:
            self._header_count.setText("1 entry")
        else:
            self._header_count.setText(f"{self._total_count} entries")

    def _populate_table(self, entries: list[dict[str, Any]]) -> None:
        self._table.setSortingEnabled(False)
        self._highlighted_row = -1
        self._table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            raw_ts = str(entry.get("timestamp") or "")
            ts_item = QTableWidgetItem(_format_timestamp(raw_ts))
            ts_item.setData(Qt.ItemDataRole.UserRole, raw_ts)

            project_item = QTableWidgetItem("")
            status_item = QTableWidgetItem("")

            for item in (ts_item, project_item, status_item):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setData(Qt.ItemDataRole.UserRole + 1, entry)

            self._table.setItem(row, 0, ts_item)
            self._table.setItem(row, 1, project_item)
            self._table.setItem(row, 2, status_item)

            project_name = str(entry.get("project_name") or "").strip() or None
            model_name = str(entry.get("model") or "")
            self._table.setCellWidget(
                row,
                1,
                _ProjectModelCell(project_name, model_name, self._table),
            )
            self._table.setCellWidget(row, 2, _StatusIconCell(self._table))
        self._table.setSortingEnabled(True)

    def _set_row_highlight(self, row: int, selected: bool) -> None:
        if row < 0 or row >= self._table.rowCount():
            return
        project_cell = self._table.cellWidget(row, 1)
        status_cell = self._table.cellWidget(row, 2)
        if isinstance(project_cell, _ProjectModelCell):
            project_cell.set_selected(selected)
        if isinstance(status_cell, _StatusIconCell):
            status_cell.set_selected(selected)

    def _on_header_clicked(self, logical_index: int) -> None:
        if logical_index == 0:
            self._table.sortItems(0, self._table.horizontalHeader().sortIndicatorOrder())

    def _update_pagination(self) -> None:
        if self._total_count == 0:
            self._page_info.setText("Showing 0 of 0")
            self._prev_btn.setEnabled(False)
            self._next_btn.setEnabled(False)
            return
        shown_from = self._current_offset + 1
        shown_to = min(self._current_offset + len(self._loaded_entries), self._total_count)
        self._page_info.setText(f"Showing {shown_from}–{shown_to} of {self._total_count}")
        self._prev_btn.setEnabled(self._current_offset > 0)
        self._next_btn.setEnabled(self._current_offset + PAGE_SIZE < self._total_count)

    def _prev_page(self) -> None:
        self._current_offset = max(0, self._current_offset - PAGE_SIZE)
        self._load_page()

    def _next_page(self) -> None:
        if self._current_offset + PAGE_SIZE < self._total_count:
            self._current_offset += PAGE_SIZE
            self._load_page()

    def _selected_row(self) -> int:
        rows = self._table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _entry_for_row(self, row: int) -> dict[str, Any] | None:
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        entry = item.data(Qt.ItemDataRole.UserRole + 1)
        return entry if isinstance(entry, dict) else None

    def _on_selection_changed(self) -> None:
        prev_row = self._highlighted_row
        row = self._selected_row()
        if prev_row >= 0 and prev_row != row:
            self._set_row_highlight(prev_row, False)
        if row >= 0:
            self._set_row_highlight(row, True)
        self._highlighted_row = row

        entry = self._entry_for_row(row)
        if entry is None:
            self._selected_entry = None
            self._set_detail_enabled(False)
            return
        self._selected_entry = entry
        self._input_detail.setPlainText(str(entry.get("input") or ""))
        self._output_detail.setPlainText(str(entry.get("output") or ""))
        self._set_detail_enabled(True)

    def _set_detail_enabled(self, enabled: bool) -> None:
        self._use_prompt_btn.setEnabled(enabled)
        self._use_both_btn.setEnabled(enabled)
        self._rerun_btn.setEnabled(enabled)

    def _focus_detail(self) -> None:
        self._output_detail.setFocus()

    def _emit_use_prompt(self) -> None:
        if not self._selected_entry:
            return
        self.use_prompt_requested.emit(str(self._selected_entry.get("input") or ""))
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
        if dest:
            shutil.copyfile(src, dest)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._table.hasFocus() or self.focusWidget() is self._table:
                self._focus_detail()
                event.accept()
                return
        super().keyPressEvent(event)
