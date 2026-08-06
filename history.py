"""
Local history of prompt optimizations.

Persistence: JSON file at ``history.json`` next to this package.
All data stays on disk locally — there is no cloud sync or remote backend.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from config import load_config
from paths import get_data_dir

HISTORY_PATH = get_data_dir() / "history.json"

_DEFAULT_SENSITIVE_KEYWORDS = ("password", "secret", "api_key", "api key", "token", "credential")


def _read_all() -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []
    try:
        with HISTORY_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_all(entries: list[dict[str, Any]]) -> None:
    with HISTORY_PATH.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Ensure optional fields exist on legacy entries."""
    normalized = dict(entry)
    if "id" not in normalized:
        normalized["id"] = str(uuid.uuid4())
    if "tags" not in normalized:
        normalized["tags"] = []
    if "excluded_from_save" not in normalized:
        normalized["excluded_from_save"] = False
    if "project_name" not in normalized:
        normalized["project_name"] = None
    return normalized


def _matches_sensitive(text: str, patterns: list[str]) -> bool:
    if not patterns:
        return False
    haystack = text.lower()
    for pattern in patterns:
        p = pattern.strip().lower()
        if not p:
            continue
        if p in haystack:
            return True
        try:
            if re.search(p, text, re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def _should_skip_save(input_text: str, excluded_from_save: bool) -> bool:
    if excluded_from_save:
        return True
    cfg = load_config()
    if not cfg.get("save_history", True):
        return True
    if cfg.get("exclude_sensitive", False):
        patterns = cfg.get("exclude_sensitive_keywords") or list(_DEFAULT_SENSITIVE_KEYWORDS)
        if _matches_sensitive(input_text, patterns):
            return True
    return False


def add_entry(
    input_text: str,
    output_text: str,
    model: str,
    *,
    tags: list[str] | None = None,
    excluded_from_save: bool = False,
    project_name: str | None = None,
) -> None:
    """Prepend a new history entry, trimming to history_limit."""
    if _should_skip_save(input_text, excluded_from_save):
        return

    cfg = load_config()
    limit = int(cfg.get("history_limit") or 50)
    entries = _read_all()
    entry: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input": input_text,
            "output": output_text,
            "model": model,
            "tags": list(tags or []),
            "excluded_from_save": False,
        }
    if project_name:
        entry["project_name"] = project_name
    entries.insert(
        0,
        entry,
    )
    _write_all(entries[: max(1, limit)])


def get_entries(limit: int | None = None) -> list[dict[str, Any]]:
    entries = [_normalize_entry(e) for e in _read_all()]
    if limit is not None:
        return entries[:limit]
    return entries


def get_entry(index_or_id: int | str) -> dict[str, Any] | None:
    """Return an entry by list index or by ``id`` string."""
    entries = get_entries()
    if isinstance(index_or_id, int):
        if 0 <= index_or_id < len(entries):
            return entries[index_or_id]
        return None
    needle = str(index_or_id)
    for entry in entries:
        if entry.get("id") == needle:
            return entry
    return None


def query_entries(
    keyword: str | None = None,
    date_from: date | datetime | None = None,
    date_to: date | datetime | None = None,
    tag: str | None = None,
    project: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """
    Filter and paginate history entries.

    Returns ``(page, total_matching_count)``.
    """
    entries = get_entries()
    filtered: list[dict[str, Any]] = []

    kw = (keyword or "").strip().lower()
    tag_filter = (tag or "").strip().lower()
    project_filter = (project or "").strip().lower()

    dt_from: datetime | None = None
    if date_from is not None:
        if isinstance(date_from, datetime):
            dt_from = date_from if date_from.tzinfo else date_from.replace(tzinfo=timezone.utc)
        else:
            dt_from = datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)

    dt_to: datetime | None = None
    if date_to is not None:
        if isinstance(date_to, datetime):
            dt_to = date_to if date_to.tzinfo else date_to.replace(tzinfo=timezone.utc)
        else:
            dt_to = datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc)

    for entry in entries:
        if tag_filter:
            entry_tags = [str(t).lower() for t in entry.get("tags") or []]
            if tag_filter not in entry_tags:
                continue

        if project_filter:
            entry_project = str(entry.get("project_name") or "").strip().lower()
            if entry_project != project_filter:
                continue

        ts = _parse_timestamp(str(entry.get("timestamp") or ""))
        if dt_from and (ts is None or ts < dt_from):
            continue
        if dt_to and (ts is None or ts > dt_to):
            continue

        if kw:
            blob = " ".join(
                [
                    str(entry.get("input") or ""),
                    str(entry.get("output") or ""),
                    str(entry.get("model") or ""),
                    " ".join(str(t) for t in entry.get("tags") or []),
                    str(entry.get("project_name") or ""),
                ]
            ).lower()
            if kw not in blob:
                continue

        filtered.append(entry)

    total = len(filtered)
    start = max(0, int(offset))
    end = start + max(0, int(limit))
    return filtered[start:end], total


def distinct_project_names() -> list[str]:
    """Return sorted unique project names from history entries."""
    names: set[str] = set()
    for entry in get_entries():
        name = str(entry.get("project_name") or "").strip()
        if name:
            names.add(name)
    return sorted(names, key=str.lower)


def history_file_path() -> Path:
    return HISTORY_PATH

def delete_entry(entry_id: str) -> bool:
    """Delete an entry by id. Returns True if deleted."""
    entries = _read_all()
    filtered = [e for e in entries if e.get("id") != entry_id]
    if len(filtered) == len(entries):
        return False
    _write_all(filtered)
    return True

