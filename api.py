"""
Gemini / Groq / OpenRouter / Anthropic API wrapper for Opti.

Provider is selected via config.json "provider". The API key stays in Python
only — never exposed to the popup UI or external scripts.
"""

from __future__ import annotations

import math
import random
import re
import time
from typing import Callable, Optional

from brand import APP_NAME, GITHUB_URL
from config import get_active_model, get_api_key, get_provider
from projects import get_active_project, get_include_project_context_in_private, touch_project_last_used
from prompt import SYSTEM_PROMPT, build_system_prompt

# Re-export so existing imports of api.SYSTEM_PROMPT keep working
__all__ = [
    "is_retryable_error",
    "optimize_prompt",
    "optimize_prompt_with_retry",
    "SYSTEM_PROMPT",
    "resolve_system_prompt",
]

_MAX_RETRY_ATTEMPTS = 4
_BASE_RETRY_DELAY_SECONDS = 1.0
_MAX_RETRY_DELAY_SECONDS = 30.0

_RETRYABLE_STATUS_CODES = {429, 502, 503, 504, 529}

# Granularity for should_cancel polling during a retry delay. Expressed as a
# fixed count of intended increments (not measured via wall-clock elapsed
# time) so the loop terminates deterministically regardless of what
# time.sleep actually does — a no-op time.sleep (as in tests) must not spin.
_CANCEL_POLL_INTERVAL_SECONDS = 0.1

_RETRYABLE_MESSAGE_PATTERNS = (
    r"rate\s*limit",
    r"too many requests",
    r"resource_exhausted",
    r"resource exhausted",
    r"overloaded",
    r"capacity",
    r"temporarily unavailable",
    r"service unavailable",
    r"high demand",
    r"try again later",
    r"quota",
    r"\b529\b",
    r"\b503\b",
    r"\b502\b",
    r"\b504\b",
    r"\b429\b",
)

_MAX_RETRIES_EXCEEDED_MESSAGE = (
    "The API is temporarily busy. Please wait a moment and try again."
)


def is_retryable_error(exc: BaseException) -> bool:
    """Return True when an API failure is worth retrying with backoff."""
    if isinstance(exc, ValueError):
        return False

    checked: list[BaseException] = [exc]
    cause = getattr(exc, "__cause__", None)
    if isinstance(cause, BaseException):
        checked.append(cause)

    for item in checked:
        for attr in ("status_code", "code", "status"):
            code = getattr(item, attr, None)
            if isinstance(code, int) and code in _RETRYABLE_STATUS_CODES:
                return True

        response = getattr(item, "response", None)
        if response is not None:
            status = getattr(response, "status_code", None)
            if isinstance(status, int) and status in _RETRYABLE_STATUS_CODES:
                return True

    message = str(exc).lower()
    return any(re.search(pattern, message) for pattern in _RETRYABLE_MESSAGE_PATTERNS)


def _retry_after_seconds(exc: BaseException) -> float | None:
    """Read Retry-After from exception metadata when available."""
    candidates: list[object] = [exc]
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        candidates.append(cause)

    for item in candidates:
        headers = getattr(item, "headers", None)
        if headers is not None:
            retry_after = headers.get("retry-after") or headers.get("Retry-After")
            if retry_after is not None:
                try:
                    return max(0.0, float(retry_after))
                except (TypeError, ValueError):
                    pass

        response = getattr(item, "response", None)
        if response is not None:
            response_headers = getattr(response, "headers", None)
            if response_headers is not None:
                retry_after = response_headers.get("retry-after") or response_headers.get(
                    "Retry-After"
                )
                if retry_after is not None:
                    try:
                        return max(0.0, float(retry_after))
                    except (TypeError, ValueError):
                        pass

    match = re.search(r"retry[- ]after[:\s]+(\d+(?:\.\d+)?)", str(exc), re.IGNORECASE)
    if match:
        try:
            return max(0.0, float(match.group(1)))
        except ValueError:
            return None
    return None


def _retry_delay_seconds(exc: BaseException, attempt: int) -> float:
    retry_after = _retry_after_seconds(exc)
    if retry_after is not None:
        return min(retry_after, _MAX_RETRY_DELAY_SECONDS)

    exponential = _BASE_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
    capped = min(exponential, _MAX_RETRY_DELAY_SECONDS)
    jitter = random.uniform(0, capped * 0.25)
    return capped + jitter


def resolve_system_prompt(*, private_mode: bool = False) -> str:
    """Build the system prompt, applying active project context when appropriate."""
    project = get_active_project()
    return build_system_prompt(
        project,
        include_in_private=get_include_project_context_in_private(),
        private_mode=private_mode,
    )


def optimize_prompt_with_retry(
    rough_prompt: str,
    model: Optional[str] = None,
    *,
    private_mode: bool = False,
    on_retry: Callable[[int, int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> str:
    """
    Call optimize_prompt with exponential backoff for transient API failures.
    """
    last_exc: BaseException | None = None

    for attempt in range(1, _MAX_RETRY_ATTEMPTS + 1):
        if should_cancel and should_cancel():
            raise RuntimeError("Cancelled")
        try:
            return optimize_prompt(rough_prompt, model=model, private_mode=private_mode)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if should_cancel and should_cancel():
                raise RuntimeError("Cancelled") from exc
            if not is_retryable_error(exc) or attempt >= _MAX_RETRY_ATTEMPTS:
                if is_retryable_error(exc) and attempt >= _MAX_RETRY_ATTEMPTS:
                    raise RuntimeError(_MAX_RETRIES_EXCEEDED_MESSAGE) from exc
                raise

            if on_retry is not None:
                on_retry(attempt + 1, _MAX_RETRY_ATTEMPTS)

            delay = _retry_delay_seconds(exc, attempt)
            if should_cancel is None:
                time.sleep(delay)
            else:
                remaining = delay
                poll = _CANCEL_POLL_INTERVAL_SECONDS
                iterations = max(1, math.ceil(delay / poll))
                for _ in range(iterations):
                    if should_cancel():
                        raise RuntimeError("Cancelled") from exc
                    chunk = min(poll, remaining)
                    time.sleep(chunk)
                    remaining -= chunk

    if last_exc is not None:
        if is_retryable_error(last_exc):
            raise RuntimeError(_MAX_RETRIES_EXCEEDED_MESSAGE) from last_exc
        raise last_exc
    raise RuntimeError(_MAX_RETRIES_EXCEEDED_MESSAGE)


def optimize_prompt(
    rough_prompt: str,
    model: Optional[str] = None,
    *,
    private_mode: bool = False,
) -> str:
    """
    Rewrite a rough prompt using the configured provider.

    Raises ValueError for empty input / missing key, or RuntimeError for API failures.
    """
    text = (rough_prompt or "").strip()
    if not text:
        raise ValueError("Prompt is empty.")

    api_key = get_api_key()
    if not api_key:
        raise ValueError(
            "No API key configured. Set it via the setup dialog or config.json."
        )

    provider = get_provider()
    model_id = model or get_active_model()
    system_prompt = resolve_system_prompt(private_mode=private_mode)

    active = get_active_project()
    if active and not (private_mode and not get_include_project_context_in_private()):
        touch_project_last_used(str(active["id"]))

    if provider == "gemini":
        return _call_gemini(api_key, model_id, text, system_prompt)
    if provider == "anthropic":
        return _call_anthropic(api_key, model_id, text, system_prompt)
    if provider in ("groq", "openrouter"):
        return _call_openai_compatible(provider, api_key, model_id, text, system_prompt)

    raise ValueError(
        f"Unknown provider '{provider}'. Use gemini, groq, openrouter, or anthropic."
    )


def _call_gemini(api_key: str, model_id: str, text: str, system_prompt: str) -> str:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError, ClientError

    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=8192,
                temperature=0.4,
            ),
        )
    except ClientError as exc:
        message = str(exc)
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        if code in (401, 403) or "API key" in message or "PERMISSION" in message.upper():
            raise RuntimeError(
                "Authentication failed. Check that your Gemini API key is valid."
            ) from exc
        if code == 429 or "RESOURCE_EXHAUSTED" in message.upper() or "quota" in message.lower():
            raise RuntimeError(
                "Rate limited by Gemini. Please wait a moment and try again."
            ) from exc
        raise RuntimeError(f"Gemini API error: {exc}") from exc
    except APIError as exc:
        raise RuntimeError(f"Gemini API error: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to reach Gemini API: {exc}") from exc

    result = (getattr(response, "text", None) or "").strip()
    if not result:
        raise RuntimeError("Gemini returned an empty response.")
    return result


def _call_anthropic(api_key: str, model_id: str, text: str, system_prompt: str) -> str:
    try:
        from anthropic import Anthropic, APIError, AuthenticationError, RateLimitError
    except ImportError as exc:
        raise RuntimeError(
            "Anthropic provider selected but the 'anthropic' package is not installed. "
            "Run: pip install anthropic"
        ) from exc

    client = Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model=model_id,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": text}],
        )
    except AuthenticationError as exc:
        raise RuntimeError(
            "Authentication failed. Check that your Anthropic API key is valid."
        ) from exc
    except RateLimitError as exc:
        raise RuntimeError(
            "Rate limited by Anthropic. Please wait a moment and try again."
        ) from exc
    except APIError as exc:
        raise RuntimeError(f"Anthropic API error: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to reach Anthropic API: {exc}") from exc

    parts: list[str] = []
    for block in message.content:
        if getattr(block, "type", None) == "text" or hasattr(block, "text"):
            parts.append(getattr(block, "text", "") or "")
    result = "".join(parts).strip()
    if not result:
        raise RuntimeError("Claude returned an empty response.")
    return result


_OPENAI_COMPAT = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "label": "Groq",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "label": "OpenRouter",
        "default_headers": {
            "HTTP-Referer": GITHUB_URL,
            "X-Title": APP_NAME,
        },
    },
}


def _call_openai_compatible(
    provider: str, api_key: str, model_id: str, text: str, system_prompt: str
) -> str:
    try:
        from openai import APIError, AuthenticationError, OpenAI, RateLimitError
    except ImportError as exc:
        raise RuntimeError(
            f"{provider} requires the 'openai' package. Run: pip install openai"
        ) from exc

    meta = _OPENAI_COMPAT[provider]
    label = meta["label"]
    kwargs: dict = {
        "api_key": api_key,
        "base_url": meta["base_url"],
    }
    if "default_headers" in meta:
        kwargs["default_headers"] = meta["default_headers"]

    client = OpenAI(**kwargs)
    try:
        completion = client.chat.completions.create(
            model=model_id,
            temperature=0.4,
            max_tokens=8192,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        )
    except AuthenticationError as exc:
        raise RuntimeError(
            f"Authentication failed. Check that your {label} API key is valid."
        ) from exc
    except RateLimitError as exc:
        raise RuntimeError(
            f"Rate limited by {label}. Please wait a moment and try again."
        ) from exc
    except APIError as exc:
        raise RuntimeError(f"{label} API error: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to reach {label} API: {exc}") from exc

    choice = completion.choices[0].message if completion.choices else None
    result = ((choice.content if choice else None) or "").strip()
    if not result:
        raise RuntimeError(f"{label} returned an empty response.")
    return result
