"""
Gemini-based transcript summarization.
"""

import os
import time
from pathlib import Path

_GEMINI_MODEL = "gemini-2.0-flash-lite"
_MIN_REQUEST_INTERVAL = 4.0  # 15 RPM = 4s between requests
_last_request_time: float = 0.0


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
    """Check if Gemini summarization is available (API key set)."""
    return bool(os.environ.get("GEMINI_API_KEY"))


def _build_prompt(transcript: str, style: str) -> str:
    if style == "bullet_points":
        instruction = (
            "Summarize the following transcript using structured bullet points. "
            "Include key topics, main points, and important takeaways. "
            "Use clear, concise language."
        )
    else:
        instruction = (
            "Provide a concise paragraph summary of the following transcript. "
            "Capture the key points and main ideas in a brief, readable format."
        )
    return f"{instruction}\n\nTranscript:\n{transcript}"


def _rate_limit() -> None:
    """Enforce minimum interval between API requests."""
    global _last_request_time  # noqa: PLW0603
    now = time.monotonic()
    wait = _MIN_REQUEST_INTERVAL - (now - _last_request_time)
    if wait > 0:
        time.sleep(wait)
    _last_request_time = time.monotonic()


def summarize_file(
    transcript_path: Path,
    summary_path: Path,
    style: str,
) -> tuple[bool, str | None]:
    """
    Read a transcript file, summarize it via Gemini, and write the summary.

    @transcript_path: Path to the transcript .txt file.
    @summary_path: Path to write the summary output.
    @style: Either 'concise' or 'bullet_points'.
    @return: (success, error_message) tuple.
    """
    try:
        from google import genai  # pylint: disable=import-outside-toplevel

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return False, "GEMINI_API_KEY not set"

        text = transcript_path.read_text(encoding="utf-8")
        if not text.strip():
            return False, "Transcript is empty"

        prompt = _build_prompt(text, style)

        _rate_limit()

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=prompt,
        )

        summary = response.text
        if not summary:
            return False, "Gemini returned empty response"

        summary_path.write_text(summary, encoding="utf-8")
        return True, None

    except Exception as e:  # pylint: disable=broad-exception-caught
        return False, str(e)
