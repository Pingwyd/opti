"""
Load and save Opti settings from config.json in the user data directory.

API keys are never logged — callers should treat get_api_key() as sensitive.

Set "provider" to one of: gemini | groq | openrouter | anthropic
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import secrets

from paths import BUNDLE_DIR, ensure_data_dir, get_data_dir

# Legacy alias — bundle/source root (not always writable when frozen)
APP_DIR = BUNDLE_DIR
CONFIG_PATH = get_data_dir() / "config.json"

# Per-provider defaults (models tuned for personal / free-tier use where possible)
PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "gemini": {
        # Free-tier friendly for new users (Gemini 3.x — 2.5 limited to legacy accounts)
        "model": "gemini-3.5-flash",
        "model_fast": "gemini-3.1-flash-lite",
        "env_keys": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "label": "Gemini",
    },
    "groq": {
        "model": "llama-3.3-70b-versatile",
        "model_fast": "llama-3.1-8b-instant",
        "env_keys": ("GROQ_API_KEY",),
        "label": "Groq",
    },
    "openrouter": {
        "model": "google/gemini-3.5-flash:free",
        "model_fast": "google/gemini-3.1-flash-lite:free",
        "env_keys": ("OPENROUTER_API_KEY",),
        "label": "OpenRouter",
    },
    "anthropic": {
        "model": "claude-sonnet-5",
        "model_fast": "claude-haiku-4-5",
        "env_keys": ("ANTHROPIC_API_KEY",),
        "label": "Anthropic",
    },
}

VALID_PROVIDERS = tuple(PROVIDER_PRESETS.keys())

# Popup keyboard shortcuts (stored in config.json, not QSettings — same persistence as other settings)
DEFAULT_HOTKEY = "Ctrl+Shift+Space"
DEFAULT_HOTKEY_COLLAPSE = "Ctrl+Alt+M"
DEFAULT_SHORTCUT_COLLAPSE = "Ctrl+Shift+M"
DEFAULT_SHORTCUT_HIDE_TRAY = "Escape"
DEFAULT_SHORTCUT_PRIVATE = "Ctrl+Shift+P"
RESCUE_WINDOW_SHORTCUT = "Ctrl+Shift+R"
DEFAULT_VOICE_PTT_SHORTCUT = "Ctrl+Space"
VALID_VOICE_MODEL_SIZES = ("tiny", "base", "small", "medium")
VALID_VOICE_TRANSCRIPTION_MODES = ("local", "cloud")
VALID_VOICE_RECORDING_MODES = ("push_to_talk", "toggle")

# Defaults: Gemini free tier (Flash), not a paid Pro model
DEFAULT_CONFIG: dict[str, Any] = {
    "provider": "gemini",
    "api_key": "",
    "hotkey": DEFAULT_HOTKEY,
    "hotkey_collapse": DEFAULT_HOTKEY_COLLAPSE,
    "model": PROVIDER_PRESETS["gemini"]["model"],
    "model_fast": PROVIDER_PRESETS["gemini"]["model_fast"],
    # "thorough" uses `model`; "fast" uses `model_fast`
    "mode": "thorough",
    "history_limit": 50,
    "save_history": True,
    "exclude_sensitive": False,
    "exclude_sensitive_keywords": [],
    "start_with_windows": False,
    "start_minimized_to_tray": True,
    "check_updates_on_launch": False,
    "persist_draft": True,
    "pill_collapsed": False,
    "window_x": None,
    "window_y": None,
    "chip_x": None,
    "chip_y": None,
    "shortcut_collapse": DEFAULT_SHORTCUT_COLLAPSE,
    "shortcut_hide_tray": DEFAULT_SHORTCUT_HIDE_TRAY,
    "shortcut_private": DEFAULT_SHORTCUT_PRIVATE,
    "auto_copy_clipboard": True,
    "auto_inject_enabled": False,
    "projects": {},
    "active_project": None,
    "include_project_context_in_private": False,
    "voice_enabled": False,
    "voice_transcription_mode": "local",
    "voice_recording_mode": "push_to_talk",
    "voice_model_size": "base",
    "voice_toggle_max_seconds": 60,
    "voice_ptt_shortcut": DEFAULT_VOICE_PTT_SHORTCUT,
}

# Migrate legacy model IDs (Claude defaults, Gemini 2.5, old OpenRouter slugs)
_LEGACY_MODEL_MAP = {
    # Claude → current Gemini defaults
    "claude-sonnet-5": "gemini-3.5-flash",
    "claude-sonnet-4-6": "gemini-3.5-flash",
    "claude-haiku-4-5": "gemini-3.1-flash-lite",
    "claude-3-5-haiku-latest": "gemini-3.1-flash-lite",
    # Gemini 2.5 → 3.x (404 for new users)
    "gemini-2.5-pro": "gemini-3.5-flash",
    "gemini-2.5-flash": "gemini-3.5-flash",
    "gemini-2.5-flash-lite": "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite-preview-09-2025": "gemini-3.1-flash-lite",
    "gemini-2.5-flash-preview-09-2025": "gemini-3.5-flash",
    "gemini-2.5-flash-preview-05-20": "gemini-3.5-flash",
    # OpenRouter free slugs
    "google/gemini-2.5-flash:free": "google/gemini-3.5-flash:free",
    "google/gemini-2.5-flash-lite:free": "google/gemini-3.1-flash-lite:free",
}


def _ensure_config_file() -> None:
    """Create config.json with defaults if it does not exist."""
    ensure_data_dir()
    if not CONFIG_PATH.exists():
        example = BUNDLE_DIR / "config.example.json"
        if example.is_file():
            CONFIG_PATH.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            save_config(deepcopy(DEFAULT_CONFIG))


def load_config() -> dict[str, Any]:
    """Return merged config (defaults + on-disk values)."""
    _ensure_config_file()
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        data = {}

    merged = deepcopy(DEFAULT_CONFIG)
    if isinstance(data, dict):
        for k, v in data.items():
            merged[k] = v

    provider = str(merged.get("provider") or "gemini").lower().strip()
    if provider not in PROVIDER_PRESETS:
        provider = "gemini"
    merged["provider"] = provider

    migrated = False
    for key in ("model", "model_fast"):
        val = merged.get(key)
        if isinstance(val, str) and val in _LEGACY_MODEL_MAP:
            merged[key] = _LEGACY_MODEL_MAP[val]
            migrated = True

    if isinstance(data, dict) and "provider" not in data:
        # Older configs had no provider field — persist gemini explicitly
        migrated = True

    stored_key = merged.get("api_key")
    if isinstance(stored_key, str) and stored_key.strip() and not secrets.is_encrypted(stored_key):
        merged["api_key"] = secrets.encrypt(stored_key.strip())
        migrated = True

    if migrated:
        save_config(merged)

    return merged


def save_config(config: dict[str, Any]) -> None:
    """Write config to disk (pretty-printed). Never prints the API key."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                existing = json.load(f) or {}
        except (json.JSONDecodeError, OSError):
            existing = {}
    existing.update(config)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
        f.write("\n")


def get_provider() -> str:
    cfg = load_config()
    provider = str(cfg.get("provider") or "gemini").lower().strip()
    return provider if provider in PROVIDER_PRESETS else "gemini"


def set_provider(provider: str, reset_models: bool = True) -> None:
    """
    Switch provider. When reset_models=True, also apply that provider's
    default thorough/fast model IDs (does not clear the API key).
    """
    provider = provider.lower().strip()
    if provider not in PROVIDER_PRESETS:
        raise ValueError(f"provider must be one of: {', '.join(VALID_PROVIDERS)}")
    cfg = load_config()
    cfg["provider"] = provider
    if reset_models:
        preset = PROVIDER_PRESETS[provider]
        cfg["model"] = preset["model"]
        cfg["model_fast"] = preset["model_fast"]
    save_config(cfg)


def get_api_key() -> str:
    """Return API key from config, or from the active provider's env vars."""
    cfg = load_config()
    stored = (cfg.get("api_key") or "").strip()
    if stored:
        try:
            return secrets.decrypt(stored)
        except (OSError, ValueError):
            return stored
    provider = get_provider()
    for env_name in PROVIDER_PRESETS[provider]["env_keys"]:
        val = (os.environ.get(env_name) or "").strip()
        if val:
            return val
    return ""


def set_api_key(api_key: str) -> None:
    cfg = load_config()
    plain = api_key.strip()
    cfg["api_key"] = secrets.encrypt(plain) if plain else ""
    save_config(cfg)


def has_api_key() -> bool:
    return bool(get_api_key())


def get_active_model() -> str:
    """Return the model ID for the current mode (thorough vs fast)."""
    cfg = load_config()
    provider = get_provider()
    preset = PROVIDER_PRESETS[provider]
    mode = (cfg.get("mode") or "thorough").lower()
    if mode == "fast":
        return cfg.get("model_fast") or preset["model_fast"]
    return cfg.get("model") or preset["model"]


def set_mode(mode: str) -> None:
    mode = mode.lower().strip()
    if mode not in ("fast", "thorough"):
        raise ValueError("mode must be 'fast' or 'thorough'")
    cfg = load_config()
    cfg["mode"] = mode
    save_config(cfg)


def provider_label() -> str:
    return PROVIDER_PRESETS[get_provider()]["label"]


def get_pill_collapsed() -> bool:
    return bool(load_config().get("pill_collapsed", False))


def set_pill_collapsed(collapsed: bool) -> None:
    cfg = load_config()
    cfg["pill_collapsed"] = bool(collapsed)
    save_config(cfg)


def get_window_position() -> tuple[int | None, int | None]:
    cfg = load_config()
    x, y = cfg.get("window_x"), cfg.get("window_y")
    if isinstance(x, int) and isinstance(y, int):
        return x, y
    # Migrate legacy chip-only position to unified window_x/y once.
    cx, cy = cfg.get("chip_x"), cfg.get("chip_y")
    if isinstance(cx, int) and isinstance(cy, int):
        cfg["window_x"] = int(cx)
        cfg["window_y"] = int(cy)
        save_config(cfg)
        return cx, cy
    return None, None


def set_window_position(x: int, y: int) -> None:
    cfg = load_config()
    cfg["window_x"] = int(x)
    cfg["window_y"] = int(y)
    save_config(cfg)


def get_chip_position() -> tuple[int | None, int | None]:
    """Return unified window position (legacy alias)."""
    return get_window_position()


def set_chip_position(x: int, y: int) -> None:
    """Write unified window position (legacy alias)."""
    set_window_position(x, y)


# Screen rect: (x, y, width, height) in global coordinates
ScreenRect = tuple[int, int, int, int]


def _rects_intersect(
    ax: int,
    ay: int,
    aw: int,
    ah: int,
    bx: int,
    by: int,
    bw: int,
    bh: int,
) -> bool:
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def window_intersects_screen(
    x: int,
    y: int,
    width: int,
    height: int,
    screen_x: int,
    screen_y: int,
    screen_width: int,
    screen_height: int,
) -> bool:
    """True when the window rect overlaps the given screen rect."""
    return _rects_intersect(
        x,
        y,
        max(1, int(width)),
        max(1, int(height)),
        screen_x,
        screen_y,
        screen_width,
        screen_height,
    )


def window_intersects_any_screen(
    x: int,
    y: int,
    width: int,
    height: int,
    screens: list[ScreenRect],
) -> bool:
    """True when the window overlaps at least one screen (ghost positions return False)."""
    for screen_x, screen_y, screen_w, screen_h in screens:
        if window_intersects_screen(x, y, width, height, screen_x, screen_y, screen_w, screen_h):
            return True
    return False


def screen_for_window(
    x: int,
    y: int,
    width: int,
    height: int,
    screens: list[ScreenRect],
) -> ScreenRect | None:
    """
    Pick the best screen for a window: center point first, then largest intersection.
  Returns None when no screen overlaps the window.
    """
    if not screens:
        return None

    w = max(1, int(width))
    h = max(1, int(height))
    cx = int(x) + w // 2
    cy = int(y) + h // 2

    for screen in screens:
        screen_x, screen_y, screen_w, screen_h = screen
        if screen_x <= cx < screen_x + screen_w and screen_y <= cy < screen_y + screen_h:
            return screen

    best: ScreenRect | None = None
    best_area = 0
    for screen_x, screen_y, screen_w, screen_h in screens:
        ix = max(int(x), screen_x)
        iy = max(int(y), screen_y)
        ix2 = min(int(x) + w, screen_x + screen_w)
        iy2 = min(int(y) + h, screen_y + screen_h)
        if ix < ix2 and iy < iy2:
            area = (ix2 - ix) * (iy2 - iy)
            if area > best_area:
                best_area = area
                best = (screen_x, screen_y, screen_w, screen_h)
    return best


def center_window_on_screen(
    width: int,
    height: int,
    screen_x: int,
    screen_y: int,
    screen_width: int,
    screen_height: int,
) -> tuple[int, int]:
    """Return top-left coords to center a window on the given screen rect."""
    w = max(1, int(width))
    h = max(1, int(height))
    x = int(screen_x) + (int(screen_width) - w) // 2
    y = int(screen_y) + max(0, (int(screen_height) - h) // 2 - 80)
    return x, y


def validate_window_position(
    x: int,
    y: int,
    width: int,
    height: int,
    screens: list[ScreenRect],
    *,
    margin: int = 24,
) -> tuple[int, int, bool]:
    """
    Clamp or rescue a window position against available screens.

    Returns (x, y, was_rescued). Ghost positions (no screen overlap) are centered
    on the primary screen (first entry in `screens`).
    """
    if not screens:
        return int(x), int(y), False

    if not window_intersects_any_screen(x, y, width, height, screens):
        primary_x, primary_y, primary_w, primary_h = screens[0]
        new_x, new_y = center_window_on_screen(
            width, height, primary_x, primary_y, primary_w, primary_h
        )
        return new_x, new_y, True

    screen = screen_for_window(x, y, width, height, screens)
    if screen is None:
        primary_x, primary_y, primary_w, primary_h = screens[0]
        new_x, new_y = center_window_on_screen(
            width, height, primary_x, primary_y, primary_w, primary_h
        )
        return new_x, new_y, True

    screen_x, screen_y, screen_w, screen_h = screen
    clamped_x, clamped_y = clamp_window_position(
        x,
        y,
        width=width,
        height=height,
        screen_x=screen_x,
        screen_y=screen_y,
        screen_width=screen_w,
        screen_height=screen_h,
        margin=margin,
    )
    return clamped_x, clamped_y, (clamped_x, clamped_y) != (int(x), int(y))


def clamp_window_position(
    x: int,
    y: int,
    *,
    width: int,
    height: int,
    screen_x: int,
    screen_y: int,
    screen_width: int,
    screen_height: int,
    margin: int = 24,
) -> tuple[int, int]:
    """
    Clamp a window top-left so at least `margin` pixels stay on the given screen rect.
    Pure function for tests and popup restore.
    """
    w = max(1, int(width))
    h = max(1, int(height))
    min_x = int(screen_x) - w + margin
    max_x = int(screen_x) + int(screen_width) - margin
    min_y = int(screen_y) - h + margin
    max_y = int(screen_y) + int(screen_height) - margin

    if min_x > max_x:
        clamped_x = int(screen_x) + (int(screen_width) - w) // 2
    else:
        clamped_x = max(min_x, min(int(x), max_x))

    if min_y > max_y:
        clamped_y = int(screen_y) + (int(screen_height) - h) // 2
    else:
        clamped_y = max(min_y, min(int(y), max_y))

    return clamped_x, clamped_y


def key_sequence_from_string(text: str) -> "QKeySequence":
    """Parse a shortcut string (e.g. from config.json) into a QKeySequence."""
    from PyQt6.QtGui import QKeySequence

    raw = (text or "").strip()
    if not raw:
        return QKeySequence()
    return QKeySequence(raw)


def normalize_shortcut_string(text: str, default: str) -> str:
    """
    Return a portable shortcut string for config.json.
    Empty or invalid sequences revert to `default`.
    """
    from PyQt6.QtGui import QKeySequence

    seq = key_sequence_from_string(text)
    if seq.isEmpty():
        return default
    return seq.toString(QKeySequence.SequenceFormat.PortableText)


def shortcuts_equal(a: str, b: str) -> bool:
    """True when both strings resolve to the same non-empty key sequence."""
    seq_a = key_sequence_from_string(a)
    seq_b = key_sequence_from_string(b)
    if seq_a.isEmpty() or seq_b.isEmpty():
        return False
    return seq_a == seq_b


def normalize_hotkey_string(text: str, default: str = DEFAULT_HOTKEY) -> str:
    """Return a portable hotkey string for config.json."""
    from PyQt6.QtGui import QKeySequence

    raw = (text or "").strip()
    if not raw:
        return default

    seq = key_sequence_from_string(raw)
    if not seq.isEmpty():
        portable = seq.toString(QKeySequence.SequenceFormat.PortableText)
        if portable:
            return portable

    legacy = _legacy_hotkey_to_portable(raw)
    if legacy:
        seq = key_sequence_from_string(legacy)
        if not seq.isEmpty():
            return seq.toString(QKeySequence.SequenceFormat.PortableText)

    return default


def _legacy_hotkey_to_portable(text: str) -> str | None:
    """Convert legacy lowercase hotkeys (ctrl+shift+space) to portable form."""
    parts = [p.strip() for p in text.split("+") if p.strip()]
    if not parts:
        return None

    mod_map = {
        "ctrl": "Ctrl",
        "control": "Ctrl",
        "alt": "Alt",
        "shift": "Shift",
        "meta": "Meta",
        "win": "Meta",
        "cmd": "Meta",
        "super": "Meta",
    }
    key_map = {
        "space": "Space",
        "tab": "Tab",
        "esc": "Esc",
        "escape": "Esc",
        "enter": "Return",
        "return": "Return",
    }

    out: list[str] = []
    for part in parts:
        low = part.lower()
        if low in mod_map:
            out.append(mod_map[low])
        elif low in key_map:
            out.append(key_map[low])
        elif len(part) == 1:
            out.append(part.upper())
        elif low.startswith("f") and low[1:].isdigit():
            out.append(part.upper())
        else:
            out.append(part.capitalize())
    return "+".join(out)


def get_hotkey() -> str:
    return normalize_hotkey_string(str(load_config().get("hotkey") or ""), DEFAULT_HOTKEY)


def set_hotkey(hotkey: str) -> None:
    cfg = load_config()
    cfg["hotkey"] = normalize_hotkey_string(hotkey, DEFAULT_HOTKEY)
    save_config(cfg)


def get_hotkey_collapse() -> str:
    return normalize_hotkey_string(
        str(load_config().get("hotkey_collapse") or ""),
        DEFAULT_HOTKEY_COLLAPSE,
    )


def set_hotkey_collapse(hotkey: str) -> None:
    cfg = load_config()
    cfg["hotkey_collapse"] = normalize_hotkey_string(hotkey, DEFAULT_HOTKEY_COLLAPSE)
    save_config(cfg)


def in_app_shortcuts_conflict(collapse: str, hide: str, private: str) -> bool:
    """True when any two in-app shortcuts resolve to the same key sequence."""
    return (
        shortcuts_equal(collapse, hide)
        or shortcuts_equal(collapse, private)
        or shortcuts_equal(hide, private)
    )


def global_hotkeys_conflict(hotkey: str, hotkey_collapse: str) -> bool:
    """True when the two global hotkeys resolve to the same key sequence."""
    return shortcuts_equal(hotkey, hotkey_collapse)


def hotkey_conflicts_with_shortcuts(
    hotkey: str,
    collapse: str,
    hide: str,
    private: str = "",
    *,
    hotkey_collapse: str = "",
) -> bool:
    """True when any global hotkey matches an in-app shortcut or each other."""
    keys = [hotkey]
    if hotkey_collapse:
        keys.append(hotkey_collapse)
    shortcuts = [collapse, hide]
    if private:
        shortcuts.append(private)
    for g in keys:
        for s in shortcuts:
            if shortcuts_equal(g, s):
                return True
    if hotkey_collapse and global_hotkeys_conflict(hotkey, hotkey_collapse):
        return True
    return False


def get_shortcut_collapse() -> str:
    return normalize_shortcut_string(
        str(load_config().get("shortcut_collapse") or ""),
        DEFAULT_SHORTCUT_COLLAPSE,
    )


def set_shortcut_collapse(shortcut: str) -> None:
    cfg = load_config()
    cfg["shortcut_collapse"] = normalize_shortcut_string(shortcut, DEFAULT_SHORTCUT_COLLAPSE)
    save_config(cfg)


def get_shortcut_hide_tray() -> str:
    return normalize_shortcut_string(
        str(load_config().get("shortcut_hide_tray") or ""),
        DEFAULT_SHORTCUT_HIDE_TRAY,
    )


def set_shortcut_hide_tray(shortcut: str) -> None:
    cfg = load_config()
    cfg["shortcut_hide_tray"] = normalize_shortcut_string(shortcut, DEFAULT_SHORTCUT_HIDE_TRAY)
    save_config(cfg)


def get_shortcut_private() -> str:
    return normalize_shortcut_string(
        str(load_config().get("shortcut_private") or ""),
        DEFAULT_SHORTCUT_PRIVATE,
    )


def set_shortcut_private(shortcut: str) -> None:
    cfg = load_config()
    cfg["shortcut_private"] = normalize_shortcut_string(shortcut, DEFAULT_SHORTCUT_PRIVATE)
    save_config(cfg)


def get_start_minimized_to_tray() -> bool:
    return bool(load_config().get("start_minimized_to_tray", True))


def get_check_updates_on_launch() -> bool:
    return bool(load_config().get("check_updates_on_launch", False))


def get_auto_copy_clipboard() -> bool:
    return bool(load_config().get("auto_copy_clipboard", True))


def set_auto_copy_clipboard(enabled: bool) -> None:
    cfg = load_config()
    cfg["auto_copy_clipboard"] = bool(enabled)
    save_config(cfg)


def get_auto_inject_enabled() -> bool:
    return bool(load_config().get("auto_inject_enabled", False))


def set_auto_inject_enabled(enabled: bool) -> None:
    cfg = load_config()
    cfg["auto_inject_enabled"] = bool(enabled)
    save_config(cfg)


def _normalize_voice_model_size(size: str) -> str:
    normalized = str(size or "base").lower().strip()
    return normalized if normalized in VALID_VOICE_MODEL_SIZES else "base"


def _normalize_voice_transcription_mode(mode: str) -> str:
    normalized = str(mode or "local").lower().strip()
    return normalized if normalized in VALID_VOICE_TRANSCRIPTION_MODES else "local"


def _normalize_voice_recording_mode(mode: str) -> str:
    normalized = str(mode or "push_to_talk").lower().strip()
    return normalized if normalized in VALID_VOICE_RECORDING_MODES else "push_to_talk"


def get_voice_enabled() -> bool:
    return bool(load_config().get("voice_enabled", False))


def get_voice_transcription_mode(*, private_mode: bool = False) -> str:
    if private_mode:
        return "local"
    return _normalize_voice_transcription_mode(
        str(load_config().get("voice_transcription_mode") or "local")
    )


def get_voice_recording_mode() -> str:
    return _normalize_voice_recording_mode(
        str(load_config().get("voice_recording_mode") or "push_to_talk")
    )


def get_voice_model_size() -> str:
    return _normalize_voice_model_size(str(load_config().get("voice_model_size") or "base"))


def get_voice_toggle_max_seconds() -> int:
    try:
        value = int(load_config().get("voice_toggle_max_seconds") or 60)
    except (TypeError, ValueError):
        value = 60
    return max(5, min(600, value))


def get_voice_ptt_shortcut() -> str:
    return normalize_shortcut_string(
        str(load_config().get("voice_ptt_shortcut") or ""),
        DEFAULT_VOICE_PTT_SHORTCUT,
    )
