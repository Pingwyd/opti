"""
Per-project context profiles stored in config.json.
"""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from config import load_config, save_config
from prompt import VALID_TRANSFORMS, normalize_transform

PROJECT_TYPES: tuple[str, ...] = (
    "",
    "Web app",
    "Mobile app",
    "Desktop app",
    "Backend",
    "CLI tool",
    "Other",
)


def parse_tech_stack_input(text: str) -> list[str]:
    """Split comma- or newline-separated tech-stack text into unique tags."""
    if not text:
        return []
    parts = re.split(r"[,\n]+", text)
    seen: set[str] = set()
    result: list[str] = []
    for part in parts:
        token = part.strip()
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(token)
    return result

MAX_PROJECTS = 100


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slug_from_name(name: str) -> str:
    """Generate a URL-safe slug from a display name."""
    slug = (name or "").lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = slug.strip("-")
    return slug or "project"


def unique_project_id(name: str, projects: dict[str, Any]) -> str:
    """Return a unique project id, suffixing duplicates (-2, -3, …)."""
    base = slug_from_name(name)
    if base not in projects:
        return base
    index = 2
    while f"{base}-{index}" in projects:
        index += 1
    return f"{base}-{index}"


def _projects_dict() -> dict[str, Any]:
    cfg = load_config()
    raw = cfg.get("projects")
    return dict(raw) if isinstance(raw, dict) else {}


def _normalize_project(project: dict[str, Any]) -> dict[str, Any]:
    tech = project.get("tech_stack")
    if not isinstance(tech, list):
        tech = []
    tech_stack = [str(t).strip() for t in tech if str(t).strip()]

    project_type = str(project.get("project_type") or "").strip()
    if project_type not in PROJECT_TYPES:
        project_type = ""

    created = str(project.get("created") or _utc_now_iso())
    return {
        "name": str(project.get("name") or "").strip(),
        "tech_stack": tech_stack,
        "project_type": project_type,
        "conventions": str(project.get("conventions") or "").strip(),
        "notes": str(project.get("notes") or "").strip(),
        "inject_process": str(project.get("inject_process") or "").strip(),
        "default_transform": normalize_transform(project.get("default_transform")),
        "created": created,
        "last_used": str(project.get("last_used") or created),
        "updated": str(project.get("updated") or created),
    }


def list_projects() -> list[dict[str, Any]]:
    """Return all projects as dicts with ``id`` included, newest last_used first."""
    projects = _projects_dict()
    items: list[dict[str, Any]] = []
    for project_id, data in projects.items():
        if not isinstance(data, dict):
            continue
        entry = _normalize_project(data)
        entry["id"] = project_id
        items.append(entry)

    def sort_key(item: dict[str, Any]) -> str:
        return str(item.get("last_used") or "")

    items.sort(key=sort_key, reverse=True)
    return items


def get_project(project_id: str) -> dict[str, Any] | None:
    projects = _projects_dict()
    data = projects.get(project_id)
    if not isinstance(data, dict):
        return None
    entry = _normalize_project(data)
    entry["id"] = project_id
    return entry


def create_project(
    *,
    name: str,
    tech_stack: list[str] | None = None,
    project_type: str = "",
    conventions: str = "",
    notes: str = "",
    default_transform: str = "optimize",
) -> str:
    """Create a project and return its id. Raises ValueError on validation failure."""
    display_name = (name or "").strip()
    if not display_name:
        raise ValueError("Project name cannot be empty.")

    cfg = load_config()
    projects = dict(cfg.get("projects") or {})
    if len(projects) >= MAX_PROJECTS:
        raise ValueError(f"Maximum of {MAX_PROJECTS} projects reached.")

    project_id = unique_project_id(display_name, projects)
    now = _utc_now_iso()
    ptype = (project_type or "").strip()
    if ptype not in PROJECT_TYPES:
        ptype = ""

    transform = normalize_transform(default_transform)
    if (default_transform or "").strip().lower() not in VALID_TRANSFORMS:
        raise ValueError(
            f"default_transform must be one of: {', '.join(VALID_TRANSFORMS)}"
        )

    projects[project_id] = {
        "name": display_name,
        "tech_stack": [t.strip() for t in (tech_stack or []) if t.strip()],
        "project_type": ptype,
        "conventions": (conventions or "").strip(),
        "notes": (notes or "").strip(),
        "default_transform": transform,
        "created": now,
        "last_used": now,
        "updated": now,
    }
    cfg["projects"] = projects
    save_config(cfg)
    return project_id


def update_project(
    project_id: str,
    *,
    name: str,
    tech_stack: list[str] | None = None,
    project_type: str = "",
    conventions: str = "",
    notes: str = "",
    inject_process: str = "",
    default_transform: str = "optimize",
) -> None:
    display_name = (name or "").strip()
    if not display_name:
        raise ValueError("Project name cannot be empty.")

    cfg = load_config()
    projects = dict(cfg.get("projects") or {})
    existing = projects.get(project_id)
    if not isinstance(existing, dict):
        raise ValueError(f"Unknown project: {project_id}")

    ptype = (project_type or "").strip()
    if ptype not in PROJECT_TYPES:
        ptype = ""

    transform = normalize_transform(default_transform)
    if (default_transform or "").strip().lower() not in VALID_TRANSFORMS:
        raise ValueError(
            f"default_transform must be one of: {', '.join(VALID_TRANSFORMS)}"
        )

    created = str(existing.get("created") or _utc_now_iso())
    projects[project_id] = {
        "name": display_name,
        "tech_stack": [t.strip() for t in (tech_stack or []) if t.strip()],
        "project_type": ptype,
        "conventions": (conventions or "").strip(),
        "notes": (notes or "").strip(),
        "inject_process": (inject_process or "").strip(),
        "default_transform": transform,
        "created": created,
        "last_used": str(existing.get("last_used") or created),
        "updated": _utc_now_iso(),
    }
    cfg["projects"] = projects
    save_config(cfg)


def delete_project(project_id: str) -> None:
    cfg = load_config()
    projects = dict(cfg.get("projects") or {})
    if project_id not in projects:
        raise ValueError(f"Unknown project: {project_id}")
    del projects[project_id]
    cfg["projects"] = projects
    if cfg.get("active_project") == project_id:
        cfg["active_project"] = None
    save_config(cfg)


def set_active_project(project_id: str | None) -> None:
    cfg = load_config()
    if project_id is not None:
        projects = cfg.get("projects") or {}
        if project_id not in projects:
            raise ValueError(f"Unknown project: {project_id}")
    cfg["active_project"] = project_id
    save_config(cfg)


def get_active_project() -> dict[str, Any] | None:
    cfg = load_config()
    active_id = cfg.get("active_project")
    if not active_id:
        return None
    return get_project(str(active_id))


def touch_project_last_used(project_id: str) -> None:
    """Update last_used timestamp for a project (e.g. after optimize)."""
    cfg = load_config()
    projects = dict(cfg.get("projects") or {})
    data = projects.get(project_id)
    if not isinstance(data, dict):
        return
    updated = deepcopy(data)
    updated["last_used"] = _utc_now_iso()
    projects[project_id] = updated
    cfg["projects"] = projects
    save_config(cfg)


def get_include_project_context_in_private() -> bool:
    return bool(load_config().get("include_project_context_in_private", False))


def set_include_project_context_in_private(enabled: bool) -> None:
    cfg = load_config()
    cfg["include_project_context_in_private"] = bool(enabled)
    save_config(cfg)
