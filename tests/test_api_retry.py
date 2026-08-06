"""Tests for API retry helpers."""

from __future__ import annotations

import math

import pytest

import api


class _FakeResponse:
    def __init__(self, status_code: int, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.headers = headers or {}


class _FakeApiError(Exception):
    def __init__(self, status_code: int, headers: dict[str, str] | None = None) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code
        self.response = _FakeResponse(status_code, headers)


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (ValueError("Prompt is empty."), False),
        (RuntimeError("Authentication failed."), False),
        (RuntimeError("Rate limited by Gemini. Please wait a moment and try again."), True),
        (RuntimeError("Rate limited by Anthropic. Please wait a moment and try again."), True),
        (RuntimeError("Rate limited by Groq. Please wait a moment and try again."), True),
        (RuntimeError("Rate limited by OpenRouter. Please wait a moment and try again."), True),
        (RuntimeError("Gemini API error: 503 service unavailable"), True),
        (RuntimeError("Anthropic API error: overloaded"), True),
        (_FakeApiError(429), True),
        (_FakeApiError(503), True),
        (_FakeApiError(529), True),
        (_FakeApiError(502), True),
        (_FakeApiError(504), True),
        (_FakeApiError(401), False),
    ],
)
def test_is_retryable_error(exc, expected):
    assert api.is_retryable_error(exc) is expected


def test_retry_after_seconds_from_headers():
    exc = _FakeApiError(429, headers={"retry-after": "2.5"})
    assert api._retry_after_seconds(exc) == 2.5


def test_optimize_prompt_with_retry_succeeds_after_transient_failure(monkeypatch):
    attempts = {"count": 0}

    def fake_optimize(prompt: str, model=None, **kwargs):  # noqa: ANN001, ARG001
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("Rate limited by Gemini. Please wait a moment and try again.")
        return "optimized"

    monkeypatch.setattr(api, "optimize_prompt", fake_optimize)
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: None)

    retry_calls: list[tuple[int, int]] = []

    result = api.optimize_prompt_with_retry(
        "hello",
        on_retry=lambda attempt, max_attempts: retry_calls.append((attempt, max_attempts)),
    )

    assert result == "optimized"
    assert attempts["count"] == 3
    assert retry_calls == [(2, 4), (3, 4)]


def test_optimize_prompt_with_retry_raises_friendly_message_after_max_attempts(monkeypatch):
    def fake_optimize(prompt: str, model=None, **kwargs):  # noqa: ANN001, ARG001
        raise RuntimeError("Rate limited by Anthropic. Please wait a moment and try again.")

    monkeypatch.setattr(api, "optimize_prompt", fake_optimize)
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="temporarily busy"):
        api.optimize_prompt_with_retry("hello")


def test_optimize_prompt_with_retry_does_not_retry_auth_errors(monkeypatch):
    attempts = {"count": 0}

    def fake_optimize(prompt: str, model=None, **kwargs):  # noqa: ANN001, ARG001
        attempts["count"] += 1
        raise RuntimeError("Authentication failed. Check that your Gemini API key is valid.")

    monkeypatch.setattr(api, "optimize_prompt", fake_optimize)
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="Authentication failed"):
        api.optimize_prompt_with_retry("hello")

    assert attempts["count"] == 1


def test_optimize_prompt_with_retry_respects_retry_after(monkeypatch):
    sleeps: list[float] = []

    def fake_optimize(prompt: str, model=None, **kwargs):  # noqa: ANN001, ARG001
        raise _FakeApiError(429, headers={"retry-after": "4"})

    monkeypatch.setattr(api, "optimize_prompt", fake_optimize)
    monkeypatch.setattr(api.time, "sleep", lambda seconds: sleeps.append(seconds))

    with pytest.raises(RuntimeError, match="temporarily busy"):
        api.optimize_prompt_with_retry("hello")

    assert sleeps == [4.0, 4.0, 4.0]


def test_optimize_prompt_with_retry_cancel_delay_does_not_busy_loop(monkeypatch):
    """A no-op time.sleep must not spin forever polling should_cancel."""
    sleeps: list[float] = []

    def fake_optimize(prompt: str, model=None, **kwargs):  # noqa: ANN001, ARG001
        raise _FakeApiError(429, headers={"retry-after": "4"})

    monkeypatch.setattr(api, "optimize_prompt", fake_optimize)
    monkeypatch.setattr(api.time, "sleep", lambda seconds: sleeps.append(seconds))

    with pytest.raises(RuntimeError, match="temporarily busy"):
        api.optimize_prompt_with_retry("hello", should_cancel=lambda: False)

    # 4.0s delay polled in fixed 0.1s increments, independent of wall-clock
    # elapsed time, across 3 retries — never an unbounded/huge list.
    assert len(sleeps) == 3 * math.ceil(4.0 / api._CANCEL_POLL_INTERVAL_SECONDS)
    assert all(s <= api._CANCEL_POLL_INTERVAL_SECONDS for s in sleeps)


def test_optimize_prompt_with_retry_cancel_mid_delay_interrupts_promptly(monkeypatch):
    """should_cancel returning True partway through a delay stops retrying."""
    calls = {"count": 0}

    def fake_optimize(prompt: str, model=None, **kwargs):  # noqa: ANN001, ARG001
        raise _FakeApiError(429, headers={"retry-after": "4"})

    def cancel_after_a_few_polls() -> bool:
        calls["count"] += 1
        return calls["count"] >= 3

    monkeypatch.setattr(api, "optimize_prompt", fake_optimize)
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="Cancelled"):
        api.optimize_prompt_with_retry("hello", should_cancel=cancel_after_a_few_polls)

    assert calls["count"] == 3
