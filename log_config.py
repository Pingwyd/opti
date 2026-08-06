"""
Central logging setup for Opti.

Redacts API keys from log records before they reach handlers.
"""

from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from paths import ensure_data_dir, get_data_dir

_LOG_DIR = get_data_dir() / "logs"
_LOG_FILE = _LOG_DIR / "opti.log"

# Common API key shapes (Gemini, Groq, OpenRouter, Anthropic, etc.)
_KEY_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)['\"]?\S+"),
    re.compile(r"(?i)(authorization\s*[:=]\s*)['\"]?\S+"),
    re.compile(r"\b(sk-[a-zA-Z0-9_-]{10,})\b"),
    re.compile(r"\b(gsk_[a-zA-Z0-9_-]{10,})\b"),
    re.compile(r"\b(AQ\.[a-zA-Z0-9_.-]{10,})\b"),
    re.compile(r"\b(dpapi:[A-Za-z0-9+/=]{20,})\b"),
)

_REDACTED = "[REDACTED]"


class RedactingFilter(logging.Filter):
    """Strip likely API keys from log message text and args."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        if record.args:
            record.args = tuple(
                self._redact(a) if isinstance(a, str) else a for a in record.args
            )
        return True

    @staticmethod
    def _redact(text: str) -> str:
        out = text
        for pattern in _KEY_PATTERNS[:2]:
            out = pattern.sub(lambda m: f"{m.group(1)}{_REDACTED}", out)
        for pattern in _KEY_PATTERNS[2:]:
            out = pattern.sub(_REDACTED, out)
        return out


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger once (console + rotating file)."""
    root = logging.getLogger()
    if getattr(setup_logging, "_configured", False):
        return

    root.setLevel(level)
    redactor = RedactingFilter()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.addFilter(redactor)
    console.setFormatter(formatter)
    root.addHandler(console)

    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            _LOG_FILE,
            maxBytes=512_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.addFilter(redactor)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        logging.getLogger(__name__).warning(
            "Could not create log file at %s; logging to stderr only", _LOG_FILE
        )

    setup_logging._configured = True  # type: ignore[attr-defined]
