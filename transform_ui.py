"""
User-facing labels and helpers for transform modes (pill UI, settings).
"""

from __future__ import annotations

from prompt import VALID_TRANSFORMS, normalize_transform

TRANSFORM_CHIP_LABELS: dict[str, str] = {
    "optimize": "Optimize",
    "tone": "Tone",
    "summarize": "Summary",
    "extract": "Extract",
    "ask": "Ask",
}

TRANSFORM_MENU_LABELS: dict[str, str] = {
    "optimize": "Optimize prompt",
    "tone": "Polish message",
    "summarize": "Summarize",
    "extract": "Extract (80/20)",
    "ask": "Ask",
}

TRANSFORM_ACTION_LABELS: dict[str, str] = {
    "optimize": "Optimize",
    "tone": "Polish",
    "summarize": "Summarize",
    "extract": "Extract",
    "ask": "Ask",
}

TRANSFORM_PLACEHOLDERS: dict[str, str] = {
    "optimize": "Write your base prompt",
    "tone": "Paste a message to polish…",
    "summarize": "Paste text to summarize…",
    "extract": "Paste text to extract what matters…",
    "ask": "Ask a question or paste text to explain…",
}

TRANSFORM_PROGRESS_LABELS: dict[str, str] = {
    "optimize": "Optimizing",
    "tone": "Polishing",
    "summarize": "Summarizing",
    "extract": "Extracting",
    "ask": "Answering",
}

TRANSFORM_CYCLE_ORDER: tuple[str, ...] = VALID_TRANSFORMS


def chip_label(transform: str) -> str:
    return TRANSFORM_CHIP_LABELS.get(normalize_transform(transform), "Optimize")


def menu_label(transform: str) -> str:
    return TRANSFORM_MENU_LABELS.get(normalize_transform(transform), "Optimize prompt")


def action_label(transform: str) -> str:
    return TRANSFORM_ACTION_LABELS.get(normalize_transform(transform), "Optimize")


def placeholder_for(transform: str) -> str:
    return TRANSFORM_PLACEHOLDERS.get(normalize_transform(transform), TRANSFORM_PLACEHOLDERS["optimize"])


def progress_verb(transform: str) -> str:
    return TRANSFORM_PROGRESS_LABELS.get(normalize_transform(transform), "Optimizing")


def next_transform(current: str) -> str:
    order = TRANSFORM_CYCLE_ORDER
    cur = normalize_transform(current)
    index = order.index(cur)
    return order[(index + 1) % len(order)]


def previous_transform(current: str) -> str:
    order = TRANSFORM_CYCLE_ORDER
    cur = normalize_transform(current)
    index = order.index(cur)
    return order[(index - 1) % len(order)]
