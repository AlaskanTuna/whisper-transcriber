"""
Core transcription logic utilizing the OpenAI Whisper model.
"""

from pathlib import Path
from typing import Any, Optional

import questionary
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn,
    MofNCompleteColumn, TimeRemainingColumn,
)


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


def transcribe_file(
    model: Any,
    input_path: Path,
    output_path: Path,
    language: Optional[str],
    task: str,
) -> tuple[bool, str | None]:
    """
    Transcribe a single audio file and write timestamped output.

    @model: Loaded Whisper model instance.
    @input_path: Path to input audio file.
    @output_path: Path to save transcription output.
    @language: Language of audio, or None for auto-detection.
    @task: Either 'transcribe' or 'translate'.
    @return: (success, error_message) tuple.
    """
    try:
        result = model.transcribe(
            str(input_path),
            language=language,
            task=task,
            verbose=False,
        )

        with open(output_path, "w", encoding="utf-8") as f:
            for segment in result["segments"]:
                start = segment["start"]
                total = int(start)
                ms = int((start - total) * 1000)
                h, m, s = total // 3600, (total % 3600) // 60, total % 60
                timestamp = f"[{h:02d}:{m:02d}:{s:02d}.{ms:03d}]"
                text = segment["text"].strip()
                f.write(f"{timestamp} {text}\n\n")

        return True, None
    except Exception as e:  # pylint: disable=broad-exception-caught
        return False, str(e)


def _check_overwrites(files: list[Path], output_dir: Path) -> list[Path]:
    """
    Check which files would overwrite existing transcripts and prompt the user.

    @files: List of audio file Paths to check.
    @output_dir: Directory where transcript files are written.
    @return: Filtered list of files to actually transcribe.
    """
    existing = []
    for f in files:
        output_path = output_dir / f"{f.stem}.txt"
        if output_path.exists():
            existing.append(f)

    if not existing:
        return files

    skip_all = "SKIP_ALL"
    names = [f.name for f in existing]
    choices = [questionary.Choice(n, checked=True) for n in names]
    choices.append(questionary.Choice(
        title=[("bold", "Skip all (keep existing)")], value=skip_all,
    ))
    answer = questionary.checkbox(
        "These files have existing transcripts. Select which to overwrite:",
        choices=choices,
        instruction="(space to toggle, enter to confirm)",
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    if skip_all in answer or not answer:
        return [f for f in files if f not in existing]

    overwrite_set = set(answer)
    return [f for f in files if f not in existing or f.name in overwrite_set]


def process_queue(
    model: Any,
    files: list[Path],
    output_dir: Path,
    language: Optional[str],
    task: str,
) -> list[dict]:
    """
    Process a queue of audio files sequentially.

    @model: Loaded Whisper model instance.
    @files: List of audio file Paths to transcribe.
    @output_dir: Directory to write transcript files.
    @language: Language of audio, or None for auto-detection.
    @task: Either 'transcribe' or 'translate'.
    @return: List of dicts with keys 'file', 'success', and 'error'.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    files = _check_overwrites(files, output_dir)
    if not files:
        return []

    results: list[dict] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        TextColumn("{task.fields[filename]}"),
    ) as progress:
        task_id = progress.add_task(
            "Transcribing", total=len(files), filename=""
        )

        for file_path in files:
            progress.update(task_id, filename=file_path.name)
            output_path = output_dir / f"{file_path.stem}.txt"
            success, error = transcribe_file(model, file_path, output_path, language, task)
            results.append({"file": file_path.name, "success": success, "error": error})
            progress.advance(task_id)

    return results
