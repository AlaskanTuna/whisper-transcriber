# src/transcriber.py

from pathlib import Path
from typing import Optional

import whisper
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn


def load_model(model_size: str) -> whisper.Whisper:
    """
    Load and return a Whisper model.

    @model_size: One of 'tiny', 'base', 'small', 'medium', 'large'.
    @return: Loaded Whisper model instance.
    """
    return whisper.load_model(model_size)


def transcribe_file(
    model: whisper.Whisper,
    input_path: Path,
    output_path: Path,
    language: Optional[str],
    task: str,
) -> bool:
    """
    Transcribe a single audio file and write timestamped output.

    @model: Loaded Whisper model instance.
    @input_path: Path to input audio file.
    @output_path: Path to save transcription output.
    @language: Language of audio, or None for auto-detection.
    @task: Either 'transcribe' or 'translate'.
    @return: True on success, False on failure.
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
                total = int(segment["start"])
                h, m, s = total // 3600, (total % 3600) // 60, total % 60
                timestamp = f"[{h:02d}:{m:02d}:{s:02d}]"
                text = segment["text"].strip()
                f.write(f"{timestamp} {text}\n\n")

        return True
    except Exception:
        return False


def process_queue(
    model: whisper.Whisper,
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
    @return: List of dicts with keys 'file' (str) and 'success' (bool).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("{task.fields[filename]}"),
    ) as progress:
        task_id = progress.add_task(
            "Transcribing", total=len(files), filename=""
        )

        for file_path in files:
            progress.update(task_id, filename=file_path.name)
            output_path = output_dir / f"{file_path.stem}.txt"
            success = transcribe_file(model, file_path, output_path, language, task)
            results.append({"file": file_path.name, "success": success})
            progress.advance(task_id)

    return results
