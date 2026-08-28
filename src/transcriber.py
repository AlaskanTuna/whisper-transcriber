"""
Core transcription logic utilizing the OpenAI Whisper model.

Returns Whisper's raw result so callers can render it in whatever formats they
need. Queue orchestration and file placement live in pipeline.py.
"""

from pathlib import Path
from typing import Any, Optional


def load_model(model_size: str) -> Any:
    """
    Load and return a Whisper model.

    @model_size: One of 'tiny', 'base', 'small', 'medium', 'large'.
    @return: Loaded Whisper model instance.
    """
    import whisper  # pylint: disable=import-outside-toplevel
    return whisper.load_model(model_size)


def get_device() -> str:
    """Return a human-readable string for the compute device."""
    import torch  # pylint: disable=import-outside-toplevel
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        return f"GPU ({name})"
    return "CPU"


def transcribe(
    model: Any,
    audio_path: Path,
    language: Optional[str],
    task: str,
) -> dict:
    """
    Transcribe one audio file.

    @model: Loaded Whisper model instance.
    @audio_path: Path to the audio file.
    @language: Language code, or None to auto-detect.
    @task: Either 'transcribe' or 'translate'.
    @return: Whisper's result dict, including 'segments' and 'language'.
    """
    return model.transcribe(
        str(audio_path),
        language=language,
        task=task,
        verbose=False,
    )
