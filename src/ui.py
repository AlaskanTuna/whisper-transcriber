# src/ui.py

import os
from pathlib import Path

import questionary
from rich.console import Console
from rich.table import Table

from src import config

console = Console()


def clear_screen() -> None:
    """
    Clear the terminal screen.
    """
    os.system("cls" if os.name == "nt" else "clear")


def _select_language() -> str:
    """
    Prompt user to select a transcription language.

    @return: Chosen language string.
    """
    choices = config.LANGUAGES + ["Other (type manually)"]
    answer = questionary.select(
        "Select language:",
        choices=choices,
        default=config.DEFAULT_LANGUAGE,
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    if answer == "Other (type manually)":
        answer = questionary.text("Enter language name (e.g. 'Polish'):").ask()
        if not answer:
            raise KeyboardInterrupt

    return answer


def _select_model_size() -> str:
    """
    Prompt user to select a Whisper model size.

    @return: Chosen model size string.
    """
    answer = questionary.select(
        "Select model size:",
        choices=config.MODEL_SIZES,
        default=config.DEFAULT_MODEL_SIZE,
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    return answer


def _select_task() -> str:
    """
    Prompt user to select the transcription task.

    @return: Either 'transcribe' or 'translate'.
    """
    answer = questionary.select(
        "Select task:",
        choices=config.TASKS,
        default=config.DEFAULT_TASK,
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    return answer


def _select_file_extension() -> str:
    """
    Prompt user to select an audio file extension.

    @return: Chosen file extension string (e.g. '.m4a').
    """
    answer = questionary.select(
        "Select audio file extension:",
        choices=config.FILE_EXTENSIONS,
        default=config.DEFAULT_FILE_EXTENSION,
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    return answer


def _confirm_directory(label: str, default: Path) -> Path:
    """
    Prompt user to confirm or change a directory path.

    @label: Display label for the prompt (e.g. 'Input directory').
    @default: Default directory path.
    @return: Confirmed Path.
    """
    answer = questionary.text(
        f"{label}:",
        default=str(default),
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    return Path(answer)


def _show_summary(settings: dict) -> bool:
    """
    Display summary table and ask for confirmation.

    @settings: Config dict to display.
    @return: True if user confirms, False otherwise.
    """
    table = Table(title="Configuration Summary")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Language", settings["language"])
    table.add_row("Model Size", settings["model_size"])
    table.add_row("Task", settings["task"])
    table.add_row("File Extension", settings["file_extension"])
    table.add_row("Input Directory", str(settings["input_dir"]))
    table.add_row("Output Directory", str(settings["output_dir"]))

    console.print()
    console.print(table)
    console.print()

    confirm = questionary.confirm("Proceed with these settings?", default=True).ask()

    if confirm is None:
        raise KeyboardInterrupt

    return confirm


def run_setup() -> dict:
    """
    Run the full TUI setup flow.

    @return: Config dict with keys: language, model_size, task, file_extension, input_dir, output_dir.
    """
    console.print("\n[bold cyan]=== Whisper Transcriber ===[/bold cyan]\n")

    language = _select_language()
    model_size = _select_model_size()
    task = _select_task()
    file_extension = _select_file_extension()
    input_dir = _confirm_directory("Input directory", config.DEFAULT_INPUT_DIR)
    output_dir = _confirm_directory("Output directory", config.DEFAULT_OUTPUT_DIR)

    settings = {
        "language": language,
        "model_size": model_size,
        "task": task,
        "file_extension": file_extension,
        "input_dir": input_dir,
        "output_dir": output_dir,
    }

    # Clear before showing summary
    clear_screen()

    if not _show_summary(settings):
        console.print("[yellow]Aborted.[/yellow]")
        raise SystemExit(0)

    return settings
