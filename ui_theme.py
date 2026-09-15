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

import zlib
from typing import Any

from PyQt6.QtGui import QFont

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
        "window_width": 620,
        "window_min_width": 620,
        "pill_height": 68,
        "pill_radius": 14,
        "chip_size": 48,
        "input_min_height": 32,
        "input_max_height": 120,
        "input_max_lines": 6,
        "result_min_height": 280,
    },
    "copy": {
        "placeholder": "Write your base prompt",
        "first_run_example": "make a react component that shows a countdown timer",
    },
}

# Flat aliases for convenience
C = DESIGN_TOKENS["color"]
R = DESIGN_TOKENS["radius"]
F = DESIGN_TOKENS["font"]
L = DESIGN_TOKENS["layout"]


def pill_stylesheet() -> str:
    """QSS for the redesigned input pill (token-driven, no legacy hex)."""
    pill_r = L.get("pill_radius", 14)
    return f"""
        QFrame#pillBar {{
            background-color: {SURFACE_RAISED};
            border: 1px solid {BORDER_CONTROL};
            border-radius: {pill_r}px;
        }}
        QFrame#pillBar[hovered="true"] {{
            border-color: {BORDER_STRONG};
        }}
        QFrame#pillBar[focused="true"] {{
            border-color: {BORDER_STRONG};
        }}
        QFrame#pillBar[collapsed="true"] {{
            border-radius: {L["chip_size"] // 2}px;
            background-color: {SURFACE_RAISED};
            min-width: {L["chip_size"]}px;
            max-width: {L["chip_size"]}px;
            min-height: {L["chip_size"]}px;
            max-height: {L["chip_size"]}px;
        }}
        QFrame#pillBar[collapsed="true"]:hover {{
            border-color: {BORDER_STRONG};
        }}
        QTextEdit#growingPromptInput {{
            background: transparent;
            border: none;
            color: {TEXT_PRIMARY};
            font-size: {F["size_base"]}px;
            padding: 1px 0 3px 0;
            selection-background-color: {CORAL_TINT_HOVER};
        }}
        QTextEdit#growingPromptInput:disabled {{
            color: {TEXT_SECONDARY};
        }}
        QLabel#pillCharCount {{
            color: {TEXT_DISABLED};
            font-family: {F["mono"]};
            font-size: {FONT_MICRO}px;
        }}
        QLabel#pillStatusLabel {{
            color: {TEXT_SECONDARY};
            font-size: {FONT_CAPTION}px;
        }}
        QLabel#pillStatusLabel[danger="true"] {{
            color: {DANGER};
        }}
        QPushButton#pillOptimizeBtn[inactive="true"] {{
            background: {INPUT_BG};
            color: {TEXT_DISABLED};
            border: 1px solid {BORDER_CONTROL};
            border-right: none;
            border-top-left-radius: 6px;
            border-bottom-left-radius: 6px;
            border-top-right-radius: 0px;
            border-bottom-right-radius: 0px;
            padding: 5px 12px;
            font-size: {F["size_sm"]}px;
        }}
        QPushButton#pillOptimizeMenuBtn[inactive="true"] {{
            background: {INPUT_BG};
            color: {TEXT_DISABLED};
            border: 1px solid {BORDER_CONTROL};
            border-left: none;
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
            border-top-left-radius: 0px;
            border-bottom-left-radius: 0px;
            padding: 5px 4px;
            font-size: {F["size_sm"]}px;
            min-width: 22px;
            max-width: 22px;
        }}
        QPushButton#pillOptimizeMenuBtn[inactive="false"] {{
            background: {CORAL};
            color: {CORAL_ON};
            border: none;
            border-left: 1px solid rgba(255, 255, 255, 0.18);
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
            border-top-left-radius: 0px;
            border-bottom-left-radius: 0px;
            padding: 5px 4px;
            font-size: {F["size_sm"]}px;
            min-width: 22px;
            max-width: 22px;
        }}
        QPushButton#pillOptimizeMenuBtn[inactive="false"]:hover {{
            background: {CORAL_HOVER};
        }}
        QPushButton#pillOptimizeMenuBtn[inactive="false"]:pressed {{
            background: {CORAL_PRESSED};
        }}
        QPushButton#pillOptimizeBtn[inactive="false"] {{
            background: {CORAL};
            color: {CORAL_ON};
            border: none;
            border-top-right-radius: 0px;
            border-bottom-right-radius: 0px;
            border-top-left-radius: 6px;
            border-bottom-left-radius: 6px;
            padding: 5px 12px;
            font-size: {F["size_sm"]}px;
            font-weight: 500;
        }}
        QPushButton#pillOptimizeBtn[inactive="false"]:hover {{
            background: {CORAL_HOVER};
        }}
        QPushButton#pillOptimizeBtn[inactive="false"]:pressed {{
            background: {CORAL_PRESSED};
        }}
        QPushButton#pillCancelBtn {{
            background: {INPUT_BG};
            color: {TEXT_BODY};
            border: 1px solid {BORDER_CONTROL};
            border-radius: 6px;
            padding: 5px 12px;
            font-size: {F["size_sm"]}px;
        }}
        QPushButton#pillCancelBtn:hover {{
            border-color: {BORDER_STRONG};
        }}
        QPushButton#pillLinkBtn {{
            background: transparent;
            color: {CORAL};
            border: none;
            padding: 0;
            font-size: {FONT_CAPTION}px;
            text-align: left;
        }}
        QPushButton#pillLinkBtn:hover {{
            text-decoration: underline;
        }}
    """


def popup_stylesheet() -> str:
    """QSS for the main Opti popup window."""
    return f"""
        QWidget {{
            font-family: {F["family"]};
        }}
        {pill_stylesheet()}
        QFrame#resultFrame {{
            background-color: {C["bg_translucent"]};
            border: 1px solid {C["border_subtle"]};
            border-radius: {R["panel"]}px;
            margin-top: 8px;
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
        QFrame#injectTargetSelector {{
            background: transparent;
        }}
        QFrame#injectTargetSelectorButton {{
            background: {INPUT_BG};
            border: 1px solid {BORDER_CONTROL};
            border-radius: {R["button"]}px;
            min-height: 28px;
        }}
        QFrame#injectTargetSelectorButton:hover {{
            border-color: {BORDER_STRONG};
        }}
        QFrame#injectTargetSelectorButton QLabel {{
            color: {C["text_muted"]};
            background: transparent;
            border: none;
        }}
        QPushButton#injectBtn {{
            background: transparent;
            color: {C["text_muted"]};
            border: 1px solid {C["border_subtle"]};
            border-radius: {R["button"]}px;
            padding: 5px 12px;
            font-size: {F["size_sm"]}px;
            font-weight: 500;
            min-height: 28px;
        }}
        QPushButton#injectBtn:hover:enabled {{
            color: {C["text"]};
            border-color: {C["border_hover"]};
            background: rgba(255, 255, 255, 0.06);
        }}
        QPushButton#injectBtn:disabled {{
            color: {C["text_muted"]};
            border-color: {C["border_subtle"]};
            opacity: 0.5;
        }}
        QFrame#targetWindowChip {{
            background: transparent;
        }}
        QFrame#targetWindowChipButton {{
            background: {INPUT_BG};
            border: 1px solid {BORDER_CONTROL};
            border-radius: 5px;
            min-height: 22px;
        }}
        QFrame#targetWindowChipButton:hover {{
            border-color: {BORDER_STRONG};
        }}
        QFrame#targetWindowChipButton QLabel {{
            color: {TEXT_SECONDARY};
            background: transparent;
            border: none;
        }}
        QMenu#targetWindowMenu {{
            background: {SURFACE_RAISED};
            border: 1px solid {BORDER_CONTROL};
            border-radius: 8px;
            padding: 4px;
        }}
        QMenu#targetWindowMenu::item {{
            padding: 6px 12px;
            border-radius: 4px;
        }}
        QMenu#targetWindowMenu::item:selected {{
            background: {CORAL_TINT};
            color: {TEXT_PRIMARY};
        }}
        QWidget#windowPickerOverlay {{
            background: transparent;
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
    """QSS for the redesigned history browser dialog (token-driven, v2)."""
    return f"""
        QDialog#historyDialog {{
            background: transparent;
        }}
        QFrame#historyShell {{
            background: {CANVAS};
            border: 1px solid {BORDER_STRONG};
            border-radius: 14px;
        }}
        QWidget#historyTitleBar {{
            background: transparent;
        }}
        QLabel#historyTitle {{
            color: {TEXT_PRIMARY};
        }}
        QLabel#historySubtitle {{
            color: {TEXT_MUTED};
        }}
        QLabel#privateModeLabel {{
            color: {TEXT_SECONDARY};
        }}
        QPushButton#historyCloseBtn {{
            background: transparent;
            border: none;
            border-radius: 6px;
        }}
        QPushButton#historyCloseBtn:hover {{
            background: {HOVER_TINT};
        }}
        QPushButton#historyExportBtn {{
            background: {SURFACE_RAISED};
            color: {TEXT_BODY};
            border: 1px solid {BORDER_CONTROL};
            border-radius: 8px;
            padding: 6px 14px;
        }}
        QPushButton#historyExportBtn:hover {{
            border-color: {BORDER_STRONG};
        }}
        QLineEdit#historySearch {{
            background: {INPUT_BG};
            border: 1px solid {BORDER_CONTROL};
            border-radius: 8px;
            color: {TEXT_BODY};
            padding: 8px 12px 8px 36px;
            selection-background-color: {CORAL_TINT_HOVER};
        }}
        QLineEdit#historySearch:hover {{
            border-color: {BORDER_STRONG};
        }}
        QLineEdit#historySearch:focus {{
            border-color: {CORAL};
        }}
        QComboBox#historyDateFilter, QComboBox#historyProjectFilter {{
            background: {INPUT_BG};
            border: 1px solid {BORDER_CONTROL};
            border-radius: 7px;
            color: {TEXT_BODY};
            padding: 6px 28px 6px 10px;
            min-height: 18px;
        }}
        QComboBox#historyDateFilter:hover, QComboBox#historyProjectFilter:hover {{
            border-color: {BORDER_STRONG};
        }}
        QComboBox#historyDateFilter:focus, QComboBox#historyProjectFilter:focus {{
            border-color: {CORAL};
        }}
        QComboBox#historyDateFilter::drop-down, QComboBox#historyProjectFilter::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 22px;
            border: none;
            background: transparent;
        }}
        QComboBox#historyDateFilter QAbstractItemView,
        QComboBox#historyProjectFilter QAbstractItemView {{
            background: {SURFACE_RAISED};
            border: 1px solid {BORDER_CONTROL};
            border-radius: 8px;
            color: {TEXT_BODY};
            padding: 4px;
            outline: none;
            selection-background-color: {CORAL_TINT_HOVER};
            selection-color: {TEXT_PRIMARY};
        }}
        QPushButton#clearFiltersBtn {{
            background: transparent;
            color: {TEXT_SECONDARY};
            border: none;
            padding: 0 4px;
            text-align: left;
        }}
        QPushButton#clearFiltersBtn:hover {{
            color: {CORAL};
            text-decoration: underline;
        }}
        QListView#historyList {{
            background: {SURFACE};
            border: 1px solid {BORDER_SUBTLE};
            border-radius: 10px;
            outline: none;
            padding: 0px;
        }}
        QListView#historyList::item {{
            border: none;
            padding: 0px;
            margin: 0px;
        }}
        QListView#historyList::item:selected {{
            background: transparent;
        }}
        QListView#historyList::item:hover {{
            background: transparent;
        }}
        QFrame#historyDetailCard {{
            background: {SURFACE};
            border: 1px solid {BORDER_SUBTLE};
            border-radius: 10px;
        }}
        QLabel#detailSectionLabel {{
            color: {TEXT_SECONDARY};
            letter-spacing: 0.6px;
        }}
        QPushButton#detailChevronBtn {{
            background: transparent;
            border: none;
            border-radius: 4px;
            padding: 2px;
        }}
        QPushButton#detailChevronBtn:hover {{
            background: {HOVER_TINT};
        }}
        QTextEdit#detailInput {{
            background: {SURFACE_RAISED};
            border: 1px solid {BORDER};
            border-radius: 6px;
            color: {TEXT_BODY};
            padding: 10px 12px;
            selection-background-color: {CORAL_TINT_HOVER};
        }}
        QTextEdit#detailOutput {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 6px;
            color: {TEXT_BODY};
            padding: 10px 12px;
            selection-background-color: {CORAL_TINT_HOVER};
        }}
        QPushButton#detailBtnPrimary {{
            background: {CORAL};
            color: {CORAL_ON};
            border: none;
            border-radius: 8px;
            padding: 8px 16px;
            font-weight: 500;
        }}
        QPushButton#detailBtnPrimary:hover:enabled {{
            background: {CORAL_HOVER};
        }}
        QPushButton#detailBtnPrimary:disabled {{
            background: {CORAL_TINT};
            color: {TEXT_DISABLED};
        }}
        QPushButton#detailBtnSecondary {{
            background: transparent;
            color: {TEXT_BODY};
            border: 1px solid {BORDER_CONTROL};
            border-radius: 8px;
            padding: 8px 14px;
        }}
        QPushButton#detailBtnSecondary:hover:enabled {{
            border-color: {BORDER_STRONG};
        }}
        QPushButton#detailBtnSecondary:disabled {{
            color: {TEXT_DISABLED};
            border-color: {BORDER_SUBTLE};
        }}
        QLabel#emptyHeadline {{
            color: {TEXT_SECONDARY};
        }}
        QLabel#emptyBody {{
            color: {TEXT_MUTED};
        }}
        QPushButton#emptyClearBtn {{
            background: transparent;
            color: {TEXT_SECONDARY};
            border: 1px solid {BORDER_CONTROL};
            border-radius: 8px;
            padding: 6px 14px;
        }}
        QPushButton#emptyClearBtn:hover {{
            border-color: {BORDER_STRONG};
            color: {TEXT_BODY};
        }}
        QSplitter#historySplitter::handle {{
            background: transparent;
            width: 10px;
        }}
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 8px;
            margin: 4px 2px 4px 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {BORDER_CONTROL};
            border-radius: 4px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {BORDER_STRONG};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            background: none;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
    """


# ---------------------------------------------------------------------------
# Settings window v2 — token-based design system
#
# Sidebar-navigated QStackedWidget, immediate-apply, no per-pane bespoke QSS.
# Every color used by settings_ui.py / widgets.py must come from this section.
# ---------------------------------------------------------------------------

# Neutrals (warm-shifted, hue 30 at ~4% saturation)
CANVAS = "#0E0D0C"
SURFACE = "#151413"
SURFACE_RAISED = "#1C1B19"
INPUT_BG = "#201F1D"

BORDER_SUBTLE = "#1E1D1B"
BORDER = "#262523"
BORDER_CONTROL = "#33312E"
BORDER_STRONG = "#454340"

TEXT_PRIMARY = "#EFEBE5"
TEXT_BODY = "#DDD8D2"
TEXT_SECONDARY = "#9A968F"
TEXT_MUTED = "#6E6B66"
TEXT_DISABLED = "#57544F"

# Coral accent
CORAL = "#E8825E"
CORAL_HOVER = "#F09A7B"
CORAL_PRESSED = "#C96A48"
CORAL_TINT = "rgba(232, 130, 94, 0.10)"
CORAL_TINT_HOVER = "rgba(232, 130, 94, 0.16)"
CORAL_ON = "#3A1C0E"  # text on a coral fill, never black

# Semantic (shifted cool so nothing reads as coral)
SUCCESS = "#4EAE84"
DANGER = "#D4485F"
DANGER_TINT = "rgba(212, 72, 95, 0.12)"
DANGER_BORDER = "rgba(212, 72, 95, 0.40)"
DANGER_TEXT = "#E8899A"  # lighter than DANGER for readable text on DANGER_TINT fills
INFO = "#5B8FD6"

HOVER_TINT = "rgba(255, 255, 255, 0.04)"

# Disabled-state knob for ToggleSwitch — distinct from TEXT_DISABLED so it
# still reads as a physical knob rather than vanishing into the track.
TOGGLE_DISABLED_KNOB = "#3A3835"

# Project badge palette (coral deliberately excluded). Index 5 = "No project".
PROJECT_COLORS: list[tuple[str, str]] = [
    ("#8FADC1", "rgba(110, 140, 160, 0.16)"),  # slate
    ("#9BB599", "rgba(122, 148, 120, 0.16)"),  # sage
    ("#AF94B8", "rgba(142, 115, 152, 0.16)"),  # plum
    ("#BFA871", "rgba(160, 139, 92, 0.16)"),  # ochre
    ("#BF929A", "rgba(160, 117, 127, 0.16)"),  # rose gray
    ("#8A867F", "rgba(255, 255, 255, 0.06)"),  # neutral / no project
]


def project_color(name: str) -> tuple[str, str]:
    """
    Deterministic (fg, bg) badge colors for a project name.

    Uses a stable hash (crc32) rather than Python's salted `hash()`, so a
    project's color survives across app restarts and processes.
    """
    if not name:
        return PROJECT_COLORS[5]
    index = zlib.crc32(name.encode("utf-8")) % 5
    return PROJECT_COLORS[index]


# Typography — two weights only (400 / 500). Sentence case everywhere.
FONT_TITLE = 17  # pane heading
FONT_SECTION = 14  # subsection heading
FONT_BODY = 13  # row label
FONT_SMALL = 12  # buttons, nav items
FONT_CAPTION = 11  # helper text, keycaps
FONT_MICRO = 10  # section eyebrows, counts

WEIGHT_REGULAR = QFont.Weight.Normal
WEIGHT_MEDIUM = QFont.Weight.Medium


def settings_font(size: int, weight: "QFont.Weight" = WEIGHT_REGULAR) -> QFont:
    """
    Build a QFont for the settings window with an explicit pixel size.

    Setting the font directly (rather than relying on QSS `font-size`) means
    QFontMetrics is accurate the instant the widget is constructed, which is
    what lets row heights scale correctly with DPI/font size instead of using
    literal pixel heights.
    """
    families = [part.strip().strip('"') for part in F["family"].split(",")]
    font = QFont()
    font.setFamilies(families)
    font.setPixelSize(size)
    font.setWeight(weight)
    return font


def settings_mono_font(size: int, weight: "QFont.Weight" = WEIGHT_REGULAR) -> QFont:
    families = [part.strip().strip('"') for part in F["mono"].split(",")]
    font = QFont()
    font.setFamilies(families)
    font.setPixelSize(size)
    font.setWeight(weight)
    return font


def settings_stylesheet() -> str:
    """
    QSS for the redesigned settings window (sidebar nav + immediate apply).

    Purely static/structural styling. Anything stateful or requiring custom
    drawing (toggle switches, steppers, keycaps, nav icons) is painted in
    widgets.py — QSS cannot reliably render those without font/icon
    dependencies, which is the defect this rewrite fixes.
    """
    return f"""
        QDialog#settingsDialog {{
            background: transparent;
        }}
        QFrame#settingsShell {{
            background: {CANVAS};
            border: 1px solid {BORDER_STRONG};
            border-radius: 14px;
        }}
        QWidget#settingsTitleBar {{
            background: transparent;
        }}
        QLabel#settingsWindowTitle {{
            color: {TEXT_PRIMARY};
        }}
        QPushButton#settingsCloseBtn {{
            background: transparent;
            border: none;
            border-radius: 6px;
        }}
        QPushButton#settingsCloseBtn:hover {{
            background: {HOVER_TINT};
        }}
        QListWidget#settingsNav {{
            background: transparent;
            border: none;
            outline: none;
            padding: 4px 8px;
        }}
        QListWidget#settingsNav::item {{
            color: {TEXT_SECONDARY};
            border-left: 2px solid transparent;
            border-radius: 0 6px 6px 0;
            padding: 8px 10px;
            margin: 1px 0;
        }}
        QListWidget#settingsNav::item:hover:!selected {{
            background: {HOVER_TINT};
            color: {TEXT_BODY};
        }}
        QListWidget#settingsNav::item:selected {{
            background: {CORAL_TINT};
            border-left: 2px solid {CORAL};
            color: {TEXT_PRIMARY};
        }}
        QWidget#settingsPane {{
            background: transparent;
        }}
        QScrollArea#settingsPaneScroll {{
            background: transparent;
            border: none;
        }}
        QScrollArea#settingsPaneScroll > QWidget > QWidget {{
            background: transparent;
        }}
        QLabel#paneTitle {{
            color: {TEXT_PRIMARY};
        }}
        QLabel#paneSubtitle {{
            color: {TEXT_SECONDARY};
        }}
        QLabel#groupEyebrow {{
            color: {TEXT_MUTED};
        }}
        QWidget#settingRow {{
            border-bottom: 1px solid {BORDER_SUBTLE};
        }}
        QWidget#settingRow[last="true"] {{
            border-bottom: none;
        }}
        QWidget#settingRow[indent="true"] {{
            border-left: 2px solid {BORDER_SUBTLE};
        }}
        QLabel#settingRowLabel {{
            color: {TEXT_BODY};
        }}
        QLabel#settingRowLabel[disabled="true"] {{
            color: {TEXT_DISABLED};
        }}
        QLabel#settingRowHelper {{
            color: {TEXT_MUTED};
        }}
        QLabel#settingRowHelper[disabled="true"] {{
            color: {TEXT_DISABLED};
        }}
        QLabel#settingRowHelper[danger="true"] {{
            color: {DANGER};
        }}
        QLabel#settingRowHelper[success="true"] {{
            color: {SUCCESS};
        }}
        QWidget#settingRowControl {{
            background: transparent;
        }}
        QWidget#keyCapRow {{
            background: transparent;
        }}
        QFrame#keyCapHost {{
            background: transparent;
            border: none;
        }}
        QFrame#keyCapHost[recording="true"] {{
            background: {INPUT_BG};
            border: 1px solid {CORAL};
            border-radius: 7px;
        }}
        QLabel#keyCapRecording {{
            color: {CORAL};
            background: transparent;
            padding: 0;
        }}
        QFrame#rowDivider {{
            background: {BORDER_SUBTLE};
            max-height: 1px;
            min-height: 1px;
            border: none;
        }}
        QLabel#footerHint {{
            color: {TEXT_MUTED};
        }}
        QPushButton#footerCloseBtn {{
            background: {SURFACE_RAISED};
            color: {TEXT_BODY};
            border: 1px solid {BORDER_CONTROL};
            border-radius: 8px;
            padding: 7px 18px;
        }}
        QPushButton#footerCloseBtn:hover {{
            border-color: {BORDER_STRONG};
            background: {SURFACE_RAISED};
        }}
        QPushButton#linkAction {{
            background: transparent;
            color: {TEXT_SECONDARY};
            border: none;
            padding: 0;
            text-align: left;
        }}
        QPushButton#linkAction:hover {{
            color: {CORAL};
            text-decoration: underline;
        }}
        QPushButton#dangerLinkAction {{
            background: transparent;
            color: {DANGER};
            border: 1px solid {DANGER_BORDER};
            border-radius: 6px;
            padding: 5px 12px;
        }}
        QPushButton#dangerLinkAction:hover {{
            background: {DANGER_TINT};
        }}
        QLabel#successCheck {{
            color: {SUCCESS};
        }}
        QLineEdit, QTextEdit {{
            background: {INPUT_BG};
            border: 1px solid {BORDER_CONTROL};
            border-radius: 7px;
            color: {TEXT_BODY};
            padding: 6px 10px;
            selection-background-color: {CORAL_TINT_HOVER};
        }}
        QLineEdit:hover, QTextEdit:hover {{
            border-color: {BORDER_STRONG};
        }}
        QLineEdit:focus, QTextEdit:focus {{
            border-color: {CORAL};
        }}
        QLineEdit:disabled, QTextEdit:disabled {{
            color: {TEXT_DISABLED};
            border-color: {BORDER_SUBTLE};
            background: {SURFACE};
        }}
        QLineEdit[danger="true"] {{
            border-color: {DANGER_BORDER};
        }}
        QTextEdit {{
            padding: 8px 10px;
        }}
        QComboBox {{
            background: {INPUT_BG};
            border: 1px solid {BORDER_CONTROL};
            border-radius: 7px;
            color: {TEXT_BODY};
            padding: 6px 10px;
            min-height: 18px;
        }}
        QComboBox:hover {{
            border-color: {BORDER_STRONG};
        }}
        QComboBox:focus {{
            border-color: {CORAL};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 22px;
            border: none;
            background: transparent;
        }}
        QComboBox QAbstractItemView {{
            background: {SURFACE_RAISED};
            border: 1px solid {BORDER_CONTROL};
            border-radius: 8px;
            color: {TEXT_BODY};
            padding: 4px;
            outline: none;
            selection-background-color: {CORAL_TINT_HOVER};
            selection-color: {TEXT_PRIMARY};
        }}
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 8px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {BORDER_CONTROL};
            border-radius: 4px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {BORDER_STRONG};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            background: none;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        QListWidget#projectsNavList {{
            background: transparent;
            border: none;
            outline: none;
        }}
        QListWidget#projectsNavList::item {{
            background: transparent;
            border: none;
            padding: 0;
            margin: 2px 0;
        }}
        QWidget#projectListItem {{
            background: transparent;
            border-left: 2px solid transparent;
            border-radius: 0 6px 6px 0;
        }}
        QWidget#projectListItem[hovered="true"][selected="false"] {{
            background: {HOVER_TINT};
        }}
        QWidget#projectListItem[selected="true"] {{
            background: {CORAL_TINT};
            border-left: 2px solid {CORAL};
        }}
        QLabel#projectCount {{
            color: {TEXT_MUTED};
        }}
        QLabel#projectDetailName {{
            color: {TEXT_PRIMARY};
        }}
        QLabel#projectDetailSaved {{
            color: {TEXT_MUTED};
        }}
        QLabel#fieldCaption {{
            color: {TEXT_SECONDARY};
        }}
        QDialog#patternsDialog {{
            background: {CANVAS};
            border: 1px solid {BORDER_STRONG};
            border-radius: 12px;
        }}
        QDialog#patternsDialog QLabel {{
            color: {TEXT_BODY};
        }}
    """


def rate_limit_dialog_stylesheet() -> str:
    """QSS for the custom rate-limit prompt (popup-adjacent alert)."""
    return f"""
        QFrame#rateLimitDialogShell {{
            background: {SURFACE_RAISED};
            border: 1px solid {BORDER_STRONG};
            border-radius: 14px;
        }}
        QLabel#rateLimitDialogTitle {{
            color: {TEXT_PRIMARY};
        }}
        QLabel#rateLimitDialogBody {{
            color: {TEXT_BODY};
        }}
        QLabel#rateLimitDialogWarning {{
            color: #E8B84A;
        }}
        QPushButton#rateLimitCloseBtn {{
            background: transparent;
            border: none;
            color: {TEXT_MUTED};
            padding: 2px 6px;
            font-size: 14px;
        }}
        QPushButton#rateLimitCloseBtn:hover {{
            color: {TEXT_PRIMARY};
        }}
        QPushButton#rateLimitPrimaryBtn {{
            background: {CORAL};
            color: {CORAL_ON};
            border: none;
            border-radius: 8px;
            padding: 8px 16px;
            font-size: {FONT_SMALL}px;
            font-weight: 500;
        }}
        QPushButton#rateLimitPrimaryBtn:hover {{
            background: {CORAL_HOVER};
        }}
        QPushButton#rateLimitPrimaryBtn:pressed {{
            background: {CORAL_PRESSED};
        }}
        QPushButton#rateLimitSecondaryBtn {{
            background: {INPUT_BG};
            color: {TEXT_BODY};
            border: 1px solid {BORDER_CONTROL};
            border-radius: 8px;
            padding: 8px 16px;
            font-size: {FONT_SMALL}px;
        }}
        QPushButton#rateLimitSecondaryBtn:hover {{
            border-color: {BORDER_STRONG};
            color: {TEXT_PRIMARY};
        }}
    """

