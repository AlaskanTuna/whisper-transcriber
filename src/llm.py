"""
Shared Gemini plumbing.

One place for the API key, the client, the rate limiter and the request call,
used by both the summarizer and the polisher.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from src.config import GEMINI_MODEL

_MIN_REQUEST_INTERVAL = 4.0
_last_request_time: float = 0.0


class LLMError(RuntimeError):
    """Raised when a Gemini request cannot be completed."""


def load_env() -> None:
    """Load .env file from project root if present."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def is_available() -> bool:
    """Check whether Gemini features are available (API key set)."""
    return bool(os.environ.get("GEMINI_API_KEY"))


def rate_limit() -> None:
    """Enforce a minimum interval between API requests."""
    global _last_request_time  # pylint: disable=global-statement
    now = time.monotonic()
    wait = _MIN_REQUEST_INTERVAL - (now - _last_request_time)
    if wait > 0:
        time.sleep(wait)
    _last_request_time = time.monotonic()


def generate(
    prompt: str,
    schema: Optional[dict] = None,
    model: Optional[str] = None,
) -> Any:
    """
    Send one prompt to Gemini and return its response.

    @prompt: The full prompt text.
    @schema: JSON schema; when given, the response is parsed and returned as a dict.
    @model: Model name override; defaults to the configured model.
    @return: Response text, or the parsed object when a schema is supplied.
    """
    from google import genai  # pylint: disable=import-outside-toplevel
    from google.genai import types  # pylint: disable=import-outside-toplevel

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise LLMError("GEMINI_API_KEY not set")

    cfg = None
    if schema is not None:
        cfg = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        )

    rate_limit()

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model or GEMINI_MODEL,
            contents=prompt,
            config=cfg,
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        raise LLMError(str(e)) from e

    text = response.text
    if not text:
        raise LLMError("Gemini returned an empty response")

    if schema is None:
        return text

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"Gemini returned malformed JSON: {e}") from e
