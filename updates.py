"""
Check for newer Opti releases on GitHub.

Uses the public GitHub REST API (no auth required for public repos).
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Literal

from brand import APP_VERSION, GITHUB_OWNER, GITHUB_REPO, GITHUB_URL

log = logging.getLogger(__name__)

GITHUB_RELEASES_LATEST = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
USER_AGENT = f"Opti/{APP_VERSION} (+{GITHUB_URL})"
REQUEST_TIMEOUT_SEC = 20


UpdateStatus = Literal["up_to_date", "update_available", "error"]


@dataclass(frozen=True)
class UpdateCheckResult:
    status: UpdateStatus
    current_version: str
    latest_version: str | None = None
    release_url: str | None = None
    error_message: str | None = None


def normalize_version(version: str) -> str:
    """Strip leading v/V and whitespace from a version or tag string."""
    return (version or "").strip().lstrip("vV").strip()


def parse_version_tuple(version: str) -> tuple[int, ...]:
    """Parse ``1.2.3`` (or ``v1.2.3-beta``) into comparable integer parts."""
    cleaned = normalize_version(version)
    parts: list[int] = []
    for segment in re.split(r"[.+_-]", cleaned):
        if not segment:
            continue
        match = re.match(r"^(\d+)", segment)
        if match:
            parts.append(int(match.group(1)))
        else:
            break
    return tuple(parts) if parts else (0,)


def is_version_newer(candidate: str, current: str) -> bool:
    return parse_version_tuple(candidate) > parse_version_tuple(current)


def _fetch_latest_release_json() -> dict:
    request = urllib.request.Request(
        GITHUB_RELEASES_LATEST,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SEC) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Unexpected GitHub API response.")
    return data


def check_for_updates(current_version: str | None = None) -> UpdateCheckResult:
    """
    Compare ``current_version`` (defaults to ``APP_VERSION``) with the latest GitHub release.
    """
    current = normalize_version(current_version or APP_VERSION)
    try:
        data = _fetch_latest_release_json()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return UpdateCheckResult(
                status="error",
                current_version=current,
                error_message="No published releases found on GitHub yet.",
            )
        log.debug("GitHub release check HTTP error", exc_info=True)
        return UpdateCheckResult(
            status="error",
            current_version=current,
            error_message=f"Could not reach GitHub (HTTP {exc.code}).",
        )
    except urllib.error.URLError as exc:
        log.debug("GitHub release check network error", exc_info=True)
        reason = getattr(exc, "reason", exc)
        return UpdateCheckResult(
            status="error",
            current_version=current,
            error_message=f"Network error: {reason}",
        )
    except (TimeoutError, json.JSONDecodeError, ValueError) as exc:
        log.debug("GitHub release check failed", exc_info=True)
        return UpdateCheckResult(
            status="error",
            current_version=current,
            error_message=str(exc) or "Update check failed.",
        )

    tag = str(data.get("tag_name") or data.get("name") or "").strip()
    latest = normalize_version(tag)
    release_url = str(data.get("html_url") or GITHUB_URL).strip()

    if not latest:
        return UpdateCheckResult(
            status="error",
            current_version=current,
            error_message="Latest release has no version tag.",
        )

    if is_version_newer(latest, current):
        return UpdateCheckResult(
            status="update_available",
            current_version=current,
            latest_version=latest,
            release_url=release_url,
        )

    return UpdateCheckResult(
        status="up_to_date",
        current_version=current,
        latest_version=latest,
        release_url=release_url,
    )
