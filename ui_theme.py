"""
Opti design tokens and Qt Style Sheet (QSS) builders.

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
        "text_secondary": "#b4b4be",
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
    """QSS for the main Opti popup window."""
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
        QPushButton#voiceMicBtn {{
            background: transparent;
            color: {C["text_muted"]};
            border: 1px solid {C["border_subtle"]};
            border-radius: 14px;
            padding: 0;
            font-size: 15px;
            min-width: 28px;
            max-width: 28px;
            min-height: 28px;
            max-height: 28px;
        }}
        QPushButton#voiceMicBtn:hover {{
            color: {C["text"]};
            border-color: {C["border_hover"]};
            background: rgba(255, 255, 255, 0.06);
        }}
        QPushButton#voiceMicBtn:disabled {{
            color: rgba(157, 157, 168, 0.45);
            border-color: rgba(255, 255, 255, 0.05);
        }}
        QPushButton#voiceMicBtn[recording="true"] {{
            color: {C["danger"]};
            border-color: rgba(255, 123, 123, 0.55);
            background: rgba(255, 123, 123, 0.14);
        }}
        QPushButton#voiceMicBtn[transcribing="true"] {{
            color: {C["accent"]};
            border-color: {C["accent_border"]};
            background: {C["accent_muted"]};
        }}
        QWidget#audioLevelMeter {{
            background: transparent;
        }}
        QLabel#voiceStatusLabel {{
            color: {C["danger"]};
            font-size: {F["size_xs"]}px;
            padding: 0;
            margin: 0;
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
        QWidget#injectRow {{
            background: transparent;
        }}
        QLabel#injectLabel {{
            color: {C["text_muted"]};
            font-size: {F["size_sm"]}px;
        }}
        QPushButton#injectBtn {{
            background: transparent;
            color: {C["text_muted"]};
            border: 1px solid {C["border_subtle"]};
            border-radius: {R["button"]}px;
            padding: 5px 12px;
            font-size: {F["size_sm"]}px;
            font-weight: 500;
        }}
        QPushButton#injectBtn:hover {{
            color: {C["text"]};
            border-color: {C["border_hover"]};
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
        QFrame#filtersBar {{
            background: {C["bg_soft"]};
            border: 1px solid {C["border_subtle"]};
            border-radius: {R["input"]}px;
        }}
        QFrame#filterSeparator {{
            background: {C["border_subtle"]};
            max-width: 1px;
            margin: 4px 4px;
        }}
        QComboBox#historyProjectFilter {{
            background: transparent;
            border: 1px solid {C["border_subtle"]};
            border-radius: {R["button"]}px;
            color: {C["text"]};
            padding: 6px 12px;
            font-size: {F["size_sm"]}px;
        }}
        QComboBox#historyProjectFilter:focus {{
            border-color: {C["border_focus"]};
        }}
        QComboBox#historyProjectFilter::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox#historyProjectFilter QAbstractItemView {{
            background: {C["bg_soft"]};
            color: {C["text"]};
            selection-background-color: {C["accent_muted"]};
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
            background: {C["accent_muted"]};
            border-color: {C["accent_border"]};
            color: {C["accent"]};
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
            background: rgba(240, 128, 96, 0.18);
            color: {C["text"]};
            border-left: 3px solid {C["accent"]};
        }}
        QTableWidget#historyTable::item:selected:hover {{
            background: rgba(240, 128, 96, 0.22);
        }}
        QLabel#modelName {{
            color: {C["text_muted"]};
            font-size: {F["size_sm"]}px;
        }}
        QLabel#statusCheck {{
            color: {C["success"]};
            font-size: 15px;
            font-weight: 700;
            min-width: 20px;
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
            padding: 8px 10px;
            selection-background-color: {C["accent_muted"]};
        }}
        QTextEdit#detailOutput {{
            font-family: {F["mono"]};
        }}
        QTextEdit#detailInput:focus, QTextEdit#detailOutput:focus {{
            border-color: {C["border_focus"]};
        }}
        QPushButton#detailBtnPrimary {{
            background: {C["accent"]};
            color: #1a1a1a;
            border: none;
            border-radius: {R["button"]}px;
            padding: 8px 16px;
            font-size: {F["size_sm"]}px;
            font-weight: 600;
        }}
        QPushButton#detailBtnPrimary:hover:enabled {{
            background: {C["accent_hover"]};
        }}
        QPushButton#detailBtnPrimary:disabled {{
            background: rgba(240, 128, 96, 0.35);
            color: rgba(26, 26, 26, 0.5);
        }}
        QPushButton#detailBtnGhost {{
            background: transparent;
            color: {C["text"]};
            border: 1px solid {C["border"]};
            border-radius: {R["button"]}px;
            padding: 8px 14px;
            font-size: {F["size_sm"]}px;
        }}
        QPushButton#detailBtnGhost:hover:enabled {{
            border-color: {C["accent_border"]};
            color: {C["accent"]};
            background: rgba(255, 255, 255, 0.03);
        }}
        QPushButton#detailBtnGhost:disabled {{
            color: rgba(157, 157, 168, 0.45);
            border-color: rgba(255, 255, 255, 0.05);
        }}
        QPushButton#detailBtnIcon {{
            background: transparent;
            color: {C["text_muted"]};
            border: 1px solid transparent;
            border-radius: {R["button"]}px;
            font-size: 18px;
            font-weight: 500;
            padding: 0;
        }}
        QPushButton#detailBtnIcon:hover:enabled {{
            color: {C["text"]};
            background: rgba(255, 255, 255, 0.06);
            border-color: {C["border_subtle"]};
        }}
        QPushButton#detailBtnIcon:disabled {{
            color: rgba(157, 157, 168, 0.45);
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
            color: #ffffff;
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -0.3px;
            padding-bottom: 2px;
        }}
        QLabel#settingsSubtitle {{
            color: {C["text_muted"]};
            font-size: {F["size_sm"]}px;
            line-height: 1.4;
        }}
        QLabel#tabDescription {{
            color: {C["text_muted"]};
            font-size: {F["size_sm"]}px;
            font-weight: 500;
            padding-bottom: 6px;
            margin-bottom: 4px;
        }}
        QLabel#sectionHeader {{
            color: {C["text_secondary"]};
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            padding-top: 10px;
            margin-bottom: 2px;
        }}
        QLabel#shortcutLabel {{
            color: {C["text"]};
            font-size: 13px;
            font-weight: 500;
        }}
        QLabel#infoIcon {{
            color: {C["text_muted"]};
            font-size: 13px;
            min-width: 14px;
            max-width: 14px;
        }}
        QLabel#projectItemName {{
            color: {C["text"]};
            font-size: 13px;
            font-weight: 600;
        }}
        QLabel#projectItemName[active="true"] {{
            color: {C["accent"]};
        }}
        QLabel#projectItemType {{
            color: {C["text_muted"]};
            font-size: 11px;
        }}
        QLabel#projectItemType[active="true"] {{
            color: {C["text_secondary"]};
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
            font-weight: 500;
        }}
        QFrame#settingsPanel {{
            background: {C["bg_soft"]};
            border: 1px solid {C["border_subtle"]};
            border-radius: {R["panel"]}px;
        }}
        QFrame#settingsPanel:hover {{
            border-color: {C["border_hover"]};
        }}
        QFrame#tagBox {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid {C["border"]};
            border-radius: {R["input"]}px;
            padding: 4px;
        }}
        QFrame#tagBox:focus-within {{
            border-color: {C["border_focus"]};
        }}
        QLineEdit#tagInlineInput {{
            background: transparent;
            border: none;
            color: {C["text"]};
            padding: 4px 6px;
            font-size: {F["size_sm"]}px;
            min-height: 24px;
        }}
        QWidget#tagChipWidget {{
            background: {C["accent_muted"]};
            border: 1px solid {C["accent_border"]};
            border-radius: 12px;
        }}
        QFrame#projectListCard {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid {C["border_subtle"]};
            border-radius: {R["input"]}px;
        }}
        QFrame#projectListCard:hover {{
            background: rgba(255, 255, 255, 0.06);
            border-color: {C["border_hover"]};
        }}
        QFrame#projectListCard[active="true"] {{
            background: {C["accent_muted"]};
            border: 1px solid {C["accent_border"]};
        }}
        QLineEdit, QSpinBox {{
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid {C["border"]};
            border-radius: {R["input"]}px;
            color: {C["text"]};
            padding: 8px 12px;
            font-size: 13px;
            min-height: 20px;
            selection-background-color: {C["accent_muted"]};
        }}
        QLineEdit:hover, QSpinBox:hover {{
            border-color: {C["border_hover"]};
            background: rgba(255, 255, 255, 0.06);
        }}
        QLineEdit:focus, QSpinBox:focus {{
            border-color: {C["border_focus"]};
            background: rgba(240, 128, 96, 0.05);
        }}
        QSpinBox::up-button, QSpinBox::down-button {{
            background: rgba(255, 255, 255, 0.06);
            border: none;
            width: 18px;
            border-radius: 3px;
            margin: 2px;
        }}
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
            background: rgba(255, 255, 255, 0.12);
        }}
        QComboBox {{
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid {C["border"]};
            border-radius: {R["input"]}px;
            color: {C["text"]};
            padding: 8px 12px;
            font-size: 13px;
            min-height: 20px;
        }}
        QComboBox:hover {{
            border-color: {C["border_hover"]};
            background: rgba(255, 255, 255, 0.06);
        }}
        QComboBox:focus {{
            border-color: {C["border_focus"]};
            background: rgba(240, 128, 96, 0.05);
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 24px;
            border: none;
            background: transparent;
        }}
        QComboBox::down-arrow {{
            image: none;
            width: 0px;
            height: 0px;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {C["text_muted"]};
            margin-right: 10px;
        }}
        QComboBox:hover::down-arrow {{
            border-top-color: {C["text"]};
        }}
        QComboBox QAbstractItemView {{
            background: {C["bg_soft"]};
            border: 1px solid {C["border"]};
            border-radius: {R["input"]}px;
            color: {C["text"]};
            padding: 4px;
            outline: none;
            selection-background-color: {C["accent_muted"]};
            selection-color: {C["accent"]};
        }}
        QCheckBox {{
            color: {C["text"]};
            font-size: {F["size_sm"]}px;
            spacing: 10px;
            padding: 2px 0;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1px solid {C["border"]};
            background: rgba(255, 255, 255, 0.04);
        }}
        QCheckBox::indicator:hover {{
            border-color: {C["border_focus"]};
            background: rgba(255, 255, 255, 0.08);
        }}
        QCheckBox::indicator:checked {{
            background-color: {C["accent"]};
            border-color: {C["accent"]};
            image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23121214' stroke-width='3.5' stroke-linecap='round' stroke-linejoin='round'><polyline points='20 6 9 17 4 12'></polyline></svg>");
        }}
        QPushButton#saveBtn {{
            border: none;
            border-radius: {R["input"]}px;
            padding: 9px 20px;
            font-size: 13px;
            font-weight: 600;
            min-height: 20px;
        }}
        QPushButton#saveBtn[dirty="false"] {{
            background: rgba(255, 255, 255, 0.07);
            color: {C["text_muted"]};
        }}
        QPushButton#saveBtn[dirty="false"]:hover {{
            background: rgba(255, 255, 255, 0.10);
            color: {C["text"]};
        }}
        QPushButton#saveBtn[dirty="true"] {{
            background: {C["accent"]};
            color: #121214;
        }}
        QPushButton#saveBtn[dirty="true"]:hover {{
            background: {C["accent_hover"]};
        }}
        QPushButton#linkBtn {{
            background: transparent;
            color: {C["text_muted"]};
            border: none;
            font-size: 12px;
            font-weight: 500;
            padding: 0;
            text-align: right;
        }}
        QPushButton#linkBtn:hover {{
            color: {C["accent"]};
        }}
        QPushButton#cancelBtn {{
            background: rgba(255, 255, 255, 0.04);
            color: {C["text"]};
            border: 1px solid {C["border"]};
            border-radius: {R["input"]}px;
            padding: 9px 18px;
            font-size: 13px;
            font-weight: 500;
            min-height: 20px;
        }}
        QPushButton#cancelBtn:hover {{
            border-color: {C["border_focus"]};
            color: {C["accent"]};
            background: rgba(240, 128, 96, 0.08);
        }}
        QScrollArea#settingsScroll {{
            background: transparent;
            border: none;
        }}
        QScrollArea#settingsScroll > QWidget > QWidget {{
            background: transparent;
        }}
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 6px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(255, 255, 255, 0.16);
            border-radius: 3px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba(240, 128, 96, 0.50);
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            background: none;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        QTabWidget#settingsTabs {{
            background: transparent;
        }}
        QTabWidget#settingsTabs::pane {{
            border: none;
            background: transparent;
            top: 0px;
        }}
        QTabBar {{
            background: transparent;
            border: none;
        }}
        QTabBar::tab {{
            background: rgba(255, 255, 255, 0.04);
            color: {C["text_muted"]};
            border: 1px solid {C["border_subtle"]};
            border-radius: 8px;
            padding: 7px 16px;
            margin-right: 6px;
            margin-top: 4px;
            margin-bottom: 8px;
            min-height: 20px;
            font-size: 13px;
            font-weight: 600;
        }}
        QTabBar::tab:hover:!selected {{
            color: {C["text"]};
            background: rgba(255, 255, 255, 0.08);
            border-color: {C["border_hover"]};
        }}
        QTabBar::tab:selected {{
            background: {C["accent_muted"]};
            color: {C["accent"]};
            border: 1px solid {C["accent_border"]};
            font-weight: 600;
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
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid {C["border"]};
            border-radius: {R["input"]}px;
            color: {C["text"]};
            padding: 6px 10px;
            font-size: 13px;
            min-height: 20px;
            max-width: 120px;
        }}
        QKeySequenceEdit:hover, QKeySequenceEdit#shortcutEdit:hover {{
            border-color: {C["border_hover"]};
            background: rgba(255, 255, 255, 0.06);
        }}
        QKeySequenceEdit:focus, QKeySequenceEdit#shortcutEdit:focus {{
            border-color: {C["border_focus"]};
            background: rgba(240, 128, 96, 0.05);
        }}
        QListWidget#tagList {{
            background: transparent;
            border: none;
            padding: 0;
        }}
        QListWidget#tagList::item {{
            border: none;
            padding: 2px;
        }}
        QLabel#tagChipLabel {{
            color: {C["text"]};
            font-size: {F["size_sm"]}px;
            font-weight: 500;
        }}
        QPushButton#tagRemoveBtn {{
            background: transparent;
            color: {C["text_muted"]};
            border: none;
            font-size: 14px;
            font-weight: 700;
            padding: 0;
        }}
        QPushButton#tagRemoveBtn:hover {{
            color: {C["accent"]};
        }}
        QListWidget#projectsList {{
            background: transparent;
            border: none;
            padding: 0;
            font-size: {F["size_sm"]}px;
        }}
        QListWidget#projectsList::item {{
            padding: 0;
            margin-bottom: 8px;
            border: none;
            background: transparent;
        }}
        QListWidget#projectsList::item:selected {{
            background: transparent;
            border: none;
        }}
    """

