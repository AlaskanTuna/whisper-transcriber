"""
Gemini-based transcript summarization.

The API key, client and rate limiting live in llm.py; this module owns the
summary prompts and the read/write wrapper.
"""

from pathlib import Path

from src.llm import LLMError, generate, is_available, load_env  # noqa: F401  (re-exported)

__all__ = ["load_env", "is_available", "summarize_text", "summarize_file"]


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


def summarize_text(transcript: str, style: str) -> str:
    """
    Summarize transcript text.

    @transcript: The transcript body.
    @style: Either 'concise' or 'bullet_points'.
    @return: The summary text.
    """
    if not transcript.strip():
        raise LLMError("Transcript is empty")
    return generate(_build_prompt(transcript, style))


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
        summary = summarize_text(transcript_path.read_text(encoding="utf-8"), style)
        summary_path.write_text(summary, encoding="utf-8")
        return True, None
    except Exception as e:  # pylint: disable=broad-exception-caught
        return False, str(e)
