"""
MetaPrompt design tokens and Qt Style Sheet (QSS) builders.

Tailwind reference (docs only, not used at runtime):
| Token              | PyQt value              | Tailwind equivalent        |
|--------------------|-------------------------|----------------------------|
| color.bg           | #141416                 | bg-[#141416]               |
| color.bg_soft      | #1c1c1f                 | bg-[#1c1c1f]               |
| color.bg_translucent | rgba(20,20,22,0.88)   | bg-zinc-950/90             |
| color.text         | #f5f5f7                 | text-zinc-100              |
| color.text_muted   | #9d9da8                 | text-zinc-400              |
| color.accent       | #F08060                 | text-[#F08060]             |
| color.accent_hover | #f59578                 | hover:text-[#f59578]       |
| color.border       | rgba(255,255,255,0.11)  | border-white/10            |
| color.border_focus | rgba(240,128,96,0.40)   | border-[#F08060]/40        |
| color.success      | #7dd4a0                 | text-emerald-300           |
| color.danger       | #ff7b7b                 | text-red-300               |
| radius.pill        | 28px                    | rounded-full               |
| radius.panel       | 16px                    | rounded-2xl                |
| radius.input       | 10px                    | rounded-lg                 |
| font.family        | Segoe UI Variable, Segoe UI | font-sans              |
| font.mono          | Cascadia Code, Consolas | font-mono                  |
"""

from __future__ import annotations

from typing import Any

DESIGN_TOKENS: dict[str, Any] = {
    "color": {
        "bg": "#141416",
        "bg_soft": "#1c1c1f",
        "bg_translucent": "rgba(20, 20, 22, 0.88)",
        "text": "#f5f5f7",
        "text_muted": "#9d9da8",
        "accent": "#F08060",
        "accent_hover": "#f59578",
        "accent_muted": "rgba(240, 128, 96, 0.14)",
        "accent_border": "rgba(240, 128, 96, 0.35)",
        "border": "rgba(255, 255, 255, 0.11)",
        "border_subtle": "rgba(255, 255, 255, 0.08)",
        "border_focus": "rgba(240, 128, 96, 0.40)",
        "border_hover": "rgba(255, 255, 255, 0.18)",
        "success": "#7dd4a0",
        "danger": "#ff7b7b",
        "result_bg": "rgba(0, 0, 0, 0.18)",
    },
    "radius": {
        "pill": 28,
        "panel": 16,
        "input": 10,
        "button": 8,
    },
    "font": {
        "family": '"Segoe UI Variable", "Segoe UI", "Inter", system-ui, sans-serif',
        "mono": '"Cascadia Code", Consolas, monospace',
        "size_xs": 11,
        "size_sm": 12,
        "size_base": 14,
        "size_lg": 18,
    },
    "layout": {
        "window_width": 640,
        "pill_height": 68,
        "chip_size": 48,
        "input_min_height": 32,
        "input_max_height": 120,
        "result_min_height": 280,
    },
    "copy": {
        "placeholder": "What can I help you with today?",
    },
}

# Flat aliases for convenience
C = DESIGN_TOKENS["color"]
R = DESIGN_TOKENS["radius"]
F = DESIGN_TOKENS["font"]
L = DESIGN_TOKENS["layout"]


def popup_stylesheet() -> str:
    """QSS for the main MetaPrompt popup window."""
    return f"""
        QWidget {{
            font-family: {F["family"]};
        }}
        QFrame#pillBar {{
            background-color: {C["bg_translucent"]};
            border: 1px solid {C["border"]};
            border-radius: {R["pill"]}px;
        }}
        QFrame#pillBar[hovered="true"] {{
            border-color: {C["border_hover"]};
            background-color: rgba(24, 24, 26, 0.92);
        }}
        QFrame#pillBar[focused="true"] {{
            border-color: {C["border_focus"]};
            background-color: rgba(26, 26, 28, 0.94);
        }}
        QFrame#pillBar[collapsed="true"] {{
            border-radius: {L["chip_size"] // 2}px;
            background-color: {C["bg_translucent"]};
            min-width: {L["chip_size"]}px;
            max-width: {L["chip_size"]}px;
            min-height: {L["chip_size"]}px;
            max-height: {L["chip_size"]}px;
        }}
        QFrame#pillBar[collapsed="true"]:hover {{
            border-color: {C["border_hover"]};
            background-color: rgba(24, 24, 26, 0.95);
        }}
        QPushButton#collapsePillBtn {{
            background: transparent;
            color: {C["text_muted"]};
            border: none;
            border-radius: 6px;
            padding: 2px 4px;
            font-size: 11px;
            min-width: 20px;
            max-width: 20px;
            min-height: 20px;
            max-height: 20px;
        }}
        QFrame#pillBar[hovered="true"] QPushButton#collapsePillBtn {{
            color: {C["text_muted"]};
        }}
        QPushButton#collapsePillBtn:hover {{
            color: {C["accent"]};
            background: rgba(255, 255, 255, 0.06);
        }}
        QPushButton#projectSelectorBtn {{
            background: transparent;
            color: {C["text_muted"]};
            border: 1px solid {C["border_subtle"]};
            border-radius: 6px;
            padding: 2px 8px;
            font-size: {F["size_xs"]}px;
            min-height: 20px;
            max-height: 22px;
        }}
        QPushButton#projectSelectorBtn:hover {{
            color: {C["text"]};
            border-color: {C["border_hover"]};
            background: rgba(255, 255, 255, 0.04);
        }}
        QPushButton#pillControlBtn {{
            background: transparent;
            color: {C["text_muted"]};
            border: none;
            border-radius: 6px;
            padding: 2px 6px;
            font-size: {F["size_xs"]}px;
            min-height: 20px;
            max-height: 22px;
        }}
        QPushButton#pillControlBtn:hover {{
            color: {C["text"]};
            background: rgba(255, 255, 255, 0.06);
        }}
        QPushButton#pillControlBtn:checked {{
            color: {C["accent"]};
            background: {C["accent_muted"]};
        }}
        QLabel#pillStatusLine {{
            color: {C["text_muted"]};
            font-size: {F["size_xs"]}px;
            padding: 0;
            margin: 0;
        }}
        QFrame#resultFrame {{
            background-color: {C["bg_translucent"]};
            border: 1px solid {C["border_subtle"]};
            border-radius: {R["panel"]}px;
            margin-top: 8px;
        }}
        QLabel#pillIcon {{
            color: {C["accent"]};
            font-size: 17px;
            font-weight: 600;
            padding: 0;
            margin: 0;
        }}
        QTextEdit#promptInput {{
            background: transparent;
            border: none;
            color: {C["text"]};
            font-size: {F["size_base"]}px;
            padding: 0 2px;
            selection-background-color: {C["accent_muted"]};
        }}
        QLabel#busyLabel {{
            color: {C["accent"]};
            font-size: {F["size_base"]}px;
            min-width: 18px;
        }}
        QLabel#statusLabel {{
            color: {C["success"]};
            font-size: {F["size_sm"]}px;
            font-weight: 500;
        }}
        QPushButton#ghostBtn {{
            background: transparent;
            color: {C["text_muted"]};
            border: none;
            border-radius: {R["button"]}px;
            padding: 5px 10px;
            font-size: {F["size_sm"]}px;
        }}
        QPushButton#ghostBtn:hover {{
            color: {C["text"]};
            background: rgba(255, 255, 255, 0.06);
        }}
        QTextEdit#resultText {{
            background: {C["result_bg"]};
            border: none;
            border-radius: {R["input"]}px;
            color: {C["text"]};
            font-family: {F["mono"]};
            font-size: 13px;
            padding: 12px;
            selection-background-color: {C["accent_muted"]};
        }}
    """


def setup_stylesheet() -> str:
    """QSS for the first-run setup dialog."""
    return f"""
        QFrame#setupShell {{
            background-color: {C["bg"]};
            border: 1px solid {C["border"]};
            border-radius: 20px;
        }}
        QLabel#setupTitle {{
            color: {C["text"]};
            font-size: {F["size_lg"]}px;
            font-weight: 600;
        }}
        QLabel#setupSubtitle {{
            color: {C["text_muted"]};
            font-size: 13px;
        }}
        QLabel#setupLabel {{
            color: {C["text_muted"]};
            font-size: {F["size_sm"]}px;
            font-weight: 500;
        }}
        QLineEdit {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid {C["border"]};
            border-radius: {R["input"]}px;
            color: {C["text"]};
            padding: 10px 14px;
            font-size: 13px;
        }}
        QLineEdit:focus {{
            border-color: {C["border_focus"]};
        }}
        QComboBox {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid {C["border"]};
            border-radius: {R["input"]}px;
            color: {C["text"]};
            padding: 8px 14px;
            font-size: 13px;
        }}
        QComboBox:focus {{
            border-color: {C["border_focus"]};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox QAbstractItemView {{
            background: {C["bg_soft"]};
            color: {C["text"]};
            selection-background-color: {C["accent_muted"]};
        }}
        QPushButton#saveBtn {{
            background: {C["accent"]};
            color: #1a1a1a;
            border: none;
            border-radius: {R["input"]}px;
            padding: 11px 20px;
            font-size: 13px;
            font-weight: 600;
        }}
        QPushButton#saveBtn:hover {{
            background: {C["accent_hover"]};
        }}
        QLabel#errorLabel {{
            color: {C["danger"]};
            font-size: {F["size_sm"]}px;
        }}
    """


def history_stylesheet() -> str:
    """QSS for the history browser dialog."""
    return f"""
        QDialog {{
            background-color: {C["bg"]};
            color: {C["text"]};
            font-family: {F["family"]};
        }}
        QLabel#historyTitle {{
            color: {C["text"]};
            font-size: {F["size_lg"]}px;
            font-weight: 600;
        }}
        QLabel#historySubtitle {{
            color: {C["text_muted"]};
            font-size: {F["size_sm"]}px;
        }}
        QLabel#chipsLabel {{
            color: {C["text_muted"]};
            font-size: {F["size_xs"]}px;
            font-weight: 500;
        }}
        QLabel#detailLabel {{
            color: {C["text_muted"]};
            font-size: {F["size_xs"]}px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }}
        QLabel#pageInfo {{
            color: {C["text_muted"]};
            font-size: {F["size_sm"]}px;
        }}
        QLabel#historyEmptyState {{
            color: {C["text_muted"]};
            font-size: {F["size_base"]}px;
            padding: 48px 24px;
        }}
        QLabel#searchIcon {{
            color: {C["text_muted"]};
            font-size: 16px;
            font-weight: 600;
            min-width: 18px;
        }}
        QFrame#searchBar {{
            background: {C["bg_soft"]};
            border: 1px solid {C["border"]};
            border-radius: {R["input"]}px;
            min-height: 40px;
        }}
        QFrame#searchBar:focus-within {{
            border-color: {C["border_focus"]};
        }}
        QLineEdit#historySearch {{
            background: transparent;
            border: none;
            color: {C["text"]};
            padding: 8px 4px;
            font-size: 13px;
            selection-background-color: {C["accent_muted"]};
        }}
        QPushButton#filterPill {{
            background: transparent;
            color: {C["text_muted"]};
            border: 1px solid {C["border_subtle"]};
            border-radius: 20px;
            padding: 6px 14px;
            font-size: {F["size_sm"]}px;
            font-weight: 500;
        }}
        QPushButton#filterPill:hover {{
            border-color: {C["border_hover"]};
            color: {C["text"]};
            background: rgba(255, 255, 255, 0.03);
        }}
        QPushButton#filterPill:checked {{
            background: rgba(255, 255, 255, 0.04);
            border-color: {C["accent_border"]};
            color: {C["text"]};
        }}
        QPushButton#filterChip {{
            background: rgba(255, 255, 255, 0.06);
            color: {C["text"]};
            border: 1px solid {C["border"]};
            border-radius: 16px;
            padding: 4px 12px;
            font-size: {F["size_xs"]}px;
        }}
        QPushButton#filterChip:hover {{
            border-color: {C["border_hover"]};
            color: {C["text"]};
            background: rgba(255, 255, 255, 0.04);
        }}
        QPushButton#headerBtn {{
            background: rgba(255, 255, 255, 0.05);
            color: {C["text"]};
            border: 1px solid {C["border"]};
            border-radius: {R["button"]}px;
            padding: 6px 14px;
            font-size: {F["size_sm"]}px;
        }}
        QPushButton#headerBtn:hover {{
            border-color: {C["accent_border"]};
            color: {C["accent"]};
        }}
        QPushButton#closeBtn {{
            background: transparent;
            color: {C["text_muted"]};
            border: 1px solid transparent;
            border-radius: {R["button"]}px;
            font-size: 18px;
            font-weight: 400;
            padding: 0;
        }}
        QPushButton#closeBtn:hover {{
            color: {C["text"]};
            background: rgba(255, 255, 255, 0.06);
            border-color: {C["border_subtle"]};
        }}
        QPushButton#pageBtn {{
            background: rgba(255, 255, 255, 0.04);
            color: {C["text"]};
            border: 1px solid {C["border"]};
            border-radius: {R["button"]}px;
            padding: 6px 14px;
            font-size: {F["size_sm"]}px;
        }}
        QPushButton#pageBtn:hover:enabled {{
            border-color: {C["accent_border"]};
            color: {C["accent"]};
        }}
        QPushButton#pageBtn:disabled {{
            color: rgba(157, 157, 168, 0.45);
            border-color: rgba(255, 255, 255, 0.05);
        }}
        QTableWidget#historyTable {{
            background: {C["bg_soft"]};
            border: 1px solid {C["border_subtle"]};
            border-radius: {R["panel"]}px;
            color: {C["text"]};
            gridline-color: transparent;
            font-size: 13px;
            alternate-background-color: rgba(255, 255, 255, 0.02);
            outline: none;
        }}
        QTableWidget#historyTable::item {{
            padding: 8px 10px;
            border: none;
        }}
        QTableWidget#historyTable::item:hover {{
            background: rgba(255, 255, 255, 0.06);
        }}
        QTableWidget#historyTable::item:selected {{
            background: rgba(240, 128, 96, 0.10);
            color: {C["text"]};
            border-left: 3px solid {C["accent"]};
        }}
        QTableWidget#historyTable::item:selected:hover {{
            background: rgba(240, 128, 96, 0.14);
        }}
        QHeaderView::section {{
            background: {C["bg_soft"]};
            color: {C["text_muted"]};
            border: none;
            border-bottom: 1px solid {C["border_subtle"]};
            padding: 10px 12px;
            font-size: {F["size_xs"]}px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}
        QHeaderView::section:hover {{
            color: {C["text"]};
        }}
        QFrame#historyDetailCard {{
            background: {C["bg_soft"]};
            border: 1px solid {C["border_subtle"]};
            border-radius: {R["panel"]}px;
        }}
        QTextEdit#detailInput, QTextEdit#detailOutput {{
            background: {C["result_bg"]};
            border: 1px solid {C["border_subtle"]};
            border-radius: {R["input"]}px;
            color: {C["text"]};
            font-size: 13px;
            padding: 10px 12px;
            selection-background-color: {C["accent_muted"]};
        }}
        QTextEdit#detailOutput {{
            font-family: {F["mono"]};
        }}
        QTextEdit#detailInput:focus, QTextEdit#detailOutput:focus {{
            border-color: {C["border_focus"]};
        }}
        QPushButton#detailBtn {{
            background: rgba(255, 255, 255, 0.05);
            color: {C["text"]};
            border: 1px solid {C["border"]};
            border-radius: {R["button"]}px;
            padding: 8px 14px;
            font-size: {F["size_sm"]}px;
        }}
        QPushButton#detailBtn:hover:enabled {{
            border-color: {C["accent_border"]};
            color: {C["accent"]};
        }}
        QPushButton#detailBtn:disabled {{
            color: rgba(157, 157, 168, 0.45);
            border-color: rgba(255, 255, 255, 0.05);
        }}
        QPushButton#detailBtnAccent {{
            background: {C["accent"]};
            color: #1a1a1a;
            border: none;
            border-radius: {R["button"]}px;
            padding: 8px 16px;
            font-size: {F["size_sm"]}px;
            font-weight: 600;
        }}
        QPushButton#detailBtnAccent:hover:enabled {{
            background: {C["accent_hover"]};
        }}
        QPushButton#detailBtnAccent:disabled {{
            background: rgba(240, 128, 96, 0.35);
            color: rgba(26, 26, 26, 0.5);
        }}
        QCheckBox {{
            color: {C["text_muted"]};
            font-size: {F["size_sm"]}px;
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1px solid {C["border"]};
            background: rgba(255, 255, 255, 0.04);
        }}
        QCheckBox::indicator:checked {{
            background: {C["accent"]};
            border-color: {C["accent"]};
        }}
        QSplitter#historySplitter::handle {{
            background: transparent;
            width: 12px;
        }}
    """


def settings_stylesheet() -> str:
    """QSS for the settings dialog."""
    return f"""
        QDialog {{
            background-color: {C["bg"]};
            color: {C["text"]};
            font-family: {F["family"]};
        }}
        QLabel#settingsTitle {{
            color: {C["text"]};
            font-size: {F["size_lg"]}px;
            font-weight: 600;
        }}
        QLabel#settingsSubtitle {{
            color: {C["text_muted"]};
            font-size: {F["size_sm"]}px;
        }}
        QLabel#tabDescription {{
            color: {C["text_muted"]};
            font-size: {F["size_sm"]}px;
            padding-bottom: 4px;
        }}
        QLabel#sectionTitle {{
            color: {C["text"]};
            font-size: 13px;
            font-weight: 600;
            padding-top: 4px;
        }}
        QLabel#fieldLabel {{
            color: {C["text_muted"]};
            font-size: {F["size_sm"]}px;
            font-weight: 500;
        }}
        QLabel#fieldHint {{
            color: {C["text_muted"]};
            font-size: {F["size_xs"]}px;
        }}
        QLabel#errorLabel {{
            color: {C["danger"]};
            font-size: {F["size_sm"]}px;
        }}
        QFrame#settingsCard {{
            background: {C["bg_soft"]};
            border: 1px solid {C["border_subtle"]};
            border-radius: {R["panel"]}px;
        }}
        QLineEdit, QSpinBox {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid {C["border"]};
            border-radius: {R["input"]}px;
            color: {C["text"]};
            padding: 8px 12px;
            font-size: 13px;
            min-height: 18px;
        }}
        QLineEdit:focus, QSpinBox:focus {{
            border-color: {C["border_focus"]};
        }}
        QSpinBox::up-button, QSpinBox::down-button {{
            background: rgba(255, 255, 255, 0.06);
            border: none;
            width: 18px;
        }}
        QComboBox {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid {C["border"]};
            border-radius: {R["input"]}px;
            color: {C["text"]};
            padding: 8px 12px;
            font-size: 13px;
        }}
        QComboBox:focus {{
            border-color: {C["border_focus"]};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox QAbstractItemView {{
            background: {C["bg_soft"]};
            color: {C["text"]};
            selection-background-color: {C["accent_muted"]};
        }}
        QCheckBox {{
            color: {C["text_muted"]};
            font-size: {F["size_sm"]}px;
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1px solid {C["border"]};
            background: rgba(255, 255, 255, 0.04);
        }}
        QCheckBox::indicator:checked {{
            background: {C["accent"]};
            border-color: {C["accent"]};
        }}
        QPushButton#saveBtn {{
            background: {C["accent"]};
            color: #1a1a1a;
            border: none;
            border-radius: {R["input"]}px;
            padding: 10px 20px;
            font-size: 13px;
            font-weight: 600;
        }}
        QPushButton#saveBtn:hover {{
            background: {C["accent_hover"]};
        }}
        QPushButton#cancelBtn {{
            background: rgba(255, 255, 255, 0.05);
            color: {C["text"]};
            border: 1px solid {C["border"]};
            border-radius: {R["input"]}px;
            padding: 10px 20px;
            font-size: 13px;
        }}
        QPushButton#cancelBtn:hover {{
            border-color: {C["accent_border"]};
            color: {C["accent"]};
        }}
        QScrollArea#settingsScroll {{
            background: transparent;
            border: none;
        }}
        QScrollArea#settingsScroll > QWidget > QWidget {{
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(255, 255, 255, 0.12);
            border-radius: 5px;
            min-height: 24px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QTabWidget#settingsTabs {{
            background: transparent;
        }}
        QTabWidget#settingsTabs::pane {{
            border: none;
            background: transparent;
            top: -1px;
        }}
        QTabWidget#settingsTabs > QTabBar::tab {{
            background: rgba(255, 255, 255, 0.04);
            color: {C["text_muted"]};
            border: 1px solid {C["border_subtle"]};
            border-bottom: none;
            border-top-left-radius: {R["button"]}px;
            border-top-right-radius: {R["button"]}px;
            padding: 8px 16px;
            margin-right: 4px;
            min-height: 20px;
            font-size: {F["size_sm"]}px;
            font-weight: 500;
        }}
        QTabWidget#settingsTabs > QTabBar::tab:selected {{
            background: {C["bg_soft"]};
            color: {C["accent"]};
            border-color: {C["accent_border"]};
        }}
        QTabWidget#settingsTabs > QTabBar::tab:hover:!selected {{
            color: {C["text"]};
            background: rgba(255, 255, 255, 0.06);
        }}
        QGroupBox#settingsGroup {{
            color: {C["text"]};
            font-size: {F["size_sm"]}px;
            font-weight: 600;
            border: 1px solid {C["border_subtle"]};
            border-radius: {R["panel"]}px;
            margin-top: 12px;
            padding-top: 8px;
            background: {C["bg_soft"]};
        }}
        QGroupBox#settingsGroup::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 14px;
            padding: 0 6px;
            color: {C["text_muted"]};
        }}
        QKeySequenceEdit, QKeySequenceEdit#shortcutEdit {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid {C["border"]};
            border-radius: {R["input"]}px;
            color: {C["text"]};
            padding: 8px 12px;
            font-size: 13px;
            min-height: 18px;
        }}
        QKeySequenceEdit:focus {{
            border-color: {C["border_focus"]};
        }}
        QListWidget#tagList {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid {C["border_subtle"]};
            border-radius: {R["input"]}px;
            padding: 4px;
        }}
        QListWidget#tagList::item {{
            border: none;
            padding: 2px;
        }}
        QLabel#tagChipLabel {{
            color: {C["text"]};
            font-size: {F["size_sm"]}px;
        }}
        QPushButton#tagRemoveBtn {{
            background: transparent;
            color: {C["text_muted"]};
            border: none;
            font-size: 14px;
            padding: 0;
        }}
        QPushButton#tagRemoveBtn:hover {{
            color: {C["accent"]};
        }}
        QListWidget#projectsList {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid {C["border_subtle"]};
            border-radius: {R["input"]}px;
            padding: 4px;
            font-size: {F["size_sm"]}px;
        }}
        QListWidget#projectsList::item {{
            padding: 8px 10px;
            border-radius: 6px;
        }}
        QListWidget#projectsList::item:selected {{
            background: {C["accent_muted"]};
            color: {C["text"]};
        }}
    """
