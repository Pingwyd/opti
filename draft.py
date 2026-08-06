"""
Local draft persistence for the prompt input bar.

Stores unsent text in ``draft.json`` next to config. Draft content is never logged.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import load_config
from paths import get_data_dir

log = logging.getLogger(__name__)

DRAFT_PATH = get_data_dir() / "draft.json"


def _persist_enabled() -> bool:
    return bool(load_config().get("persist_draft", True))


def save_draft(text: str) -> None:
    """Persist draft text. Skips whitespace-only input."""
    if not _persist_enabled():
        return
    if not text or not text.strip():
        return
    payload: dict[str, Any] = {
        "text": text,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DRAFT_PATH.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError:
        log.warning("Failed to save draft", exc_info=True)


def load_draft() -> str | None:
    """Return saved draft text, or None if missing / disabled / empty."""
    if not _persist_enabled():
        return None
    if not DRAFT_PATH.exists():
        return None
    try:
        with DRAFT_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    return text


def clear_draft() -> None:
    """Remove the on-disk draft file."""
    try:
        if DRAFT_PATH.exists():
            DRAFT_PATH.unlink()
    except OSError:
        log.warning("Failed to clear draft", exc_info=True)
