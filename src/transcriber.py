# src/transcriber.py

from pathlib import Path

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
    language: str,
    task: str,
) -> bool:
    """
    Transcribe a single audio file and write timestamped output.

    @model: Loaded Whisper model instance.
    @input_path: Path to input audio file.
    @output_path: Path to save transcription output.
    @language: Language of audio (e.g. 'Japanese').
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
                timestamp = f"[{segment['start']:.1f}s]"
                text = segment["text"].strip()
                f.write(f"{timestamp} {text}\n\n")

        return True
    except Exception:
        return False


def process_directory(
    model: whisper.Whisper,
    input_dir: Path,
    output_dir: Path,
    language: str,
    task: str,
    file_extension: str,
) -> int:
    """
    Process all matching audio files in a directory.

    @model: Loaded Whisper model instance.
    @input_dir: Directory containing audio files.
    @output_dir: Directory to write transcript files.
    @language: Language of audio.
    @task: Either 'transcribe' or 'translate'.
    @file_extension: Audio file extension to match (e.g. '.m4a').
    @return: Number of files successfully transcribed.
    """
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(input_dir.glob(f"*{file_extension}"))
    if not files:
        return 0

    success_count = 0

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

            if transcribe_file(model, file_path, output_path, language, task):
                success_count += 1

            progress.advance(task_id)

    return success_count
