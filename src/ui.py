# src/ui.py

import os
from pathlib import Path
from typing import Optional

import questionary
from rich.console import Console
from rich.table import Table

from src import config

console = Console()

_BACK = "BACK"
_EXIT = "EXIT"
_BACK_LABEL = [("bold", "BACK")]
_EXIT_LABEL = [("bold", "EXIT")]


def clear_screen() -> None:
    """
    Clear the terminal screen.
    """
    os.system("cls" if os.name == "nt" else "clear")


def _scan_audio_files() -> list[Path]:
    """
    Scan the input directory for files matching any supported extension.

    @return: Sorted list of audio file Paths found in DEFAULT_INPUT_DIR.
    """
    files: list[Path] = []
    for ext in config.FILE_EXTENSIONS:
        files.extend(config.DEFAULT_INPUT_DIR.glob(f"*{ext}"))
    return sorted(set(files), key=lambda p: p.name.lower())


def _select_language() -> Optional[str]:
    """
    Prompt user to select a transcription language.

    @return: Language string, None for auto-detect, or _EXIT/_BACK sentinel.
    """
    choices = [config.AUTO_DETECT] + config.LANGUAGES + [
        questionary.Choice(title=_EXIT_LABEL, value=_EXIT)
    ]
    answer = questionary.select(
        "Select language:",
        choices=choices,
        default=config.DEFAULT_LANGUAGE,
        instruction="",
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    return answer


def _select_model_size() -> str:
    """
    Prompt user to select a Whisper model size.

    @return: Model size string or _BACK sentinel.
    """
    choices = config.MODEL_SIZES + [
        questionary.Choice(title=_BACK_LABEL, value=_BACK)
    ]
    answer = questionary.select(
        "Select model size:",
        choices=choices,
        default=config.DEFAULT_MODEL_SIZE,
        instruction="",
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    return answer


def _select_task() -> str:
    """
    Prompt user to select the transcription task.

    @return: 'transcribe', 'translate', or _BACK sentinel.
    """
    choices = config.TASKS + [
        questionary.Choice(title=_BACK_LABEL, value=_BACK)
    ]
    answer = questionary.select(
        "Select task:",
        choices=choices,
        default=config.DEFAULT_TASK,
        instruction="",
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    return answer


def _select_files(available: list[Path]) -> list[Path] | str:
    """
    Prompt user to select one or more audio files via checkbox.

    @available: List of audio file Paths to choose from.
    @return: List of selected Paths, or _BACK sentinel.
    """
    choices = [questionary.Choice(f.name, value=str(f)) for f in available]
    choices.append(questionary.Choice(title=_BACK_LABEL, value=_BACK))

    answer = questionary.checkbox(
        "Select audio files (space to toggle, enter to confirm):",
        choices=choices,
        instruction="",
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    if _BACK in answer:
        return _BACK

    if not answer:
        return _BACK

    return [Path(p) for p in answer]


def _show_summary(settings: dict) -> bool:
    """
    Display summary table and ask for confirmation.

    @settings: Config dict to display.
    @return: True if user confirms, False otherwise.
    """
    table = Table(title="Configuration Summary")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    lang_display = settings["language"] if settings["language"] else "Auto (detect)"
    table.add_row("Language", lang_display)
    table.add_row("Model Size", settings["model_size"])
    table.add_row("Task", settings["task"])
    table.add_row("Files", str(len(settings["files"])))
    table.add_row("Input Directory", str(config.DEFAULT_INPUT_DIR))
    table.add_row("Output Directory", str(config.DEFAULT_OUTPUT_DIR))

    console.print()
    console.print(table)
    console.print()

    confirm = questionary.confirm("Proceed with these settings?", default=True).ask()

    if confirm is None:
        raise KeyboardInterrupt

    return confirm


def run_setup() -> dict | None:
    """
    Run the full TUI setup flow with step-based Back/Exit navigation.

    @return: Config dict with keys: language, model_size, task, files.
             Returns None if user chooses Exit.
    """
    step = 0
    language: Optional[str] = None
    model_size: str = ""
    task: str = ""
    files: list[Path] = []

    while True:
        if step == 0:
            clear_screen()
            console.print("\n[bold cyan]=== Whisper Transcriber ===[/bold cyan]\n")
            answer = _select_language()
            if answer == _EXIT:
                return None
            language = None if answer == config.AUTO_DETECT else answer
            step = 1

        elif step == 1:
            answer = _select_model_size()
            if answer == _BACK:
                step = 0
                continue
            model_size = answer
            step = 2

        elif step == 2:
            answer = _select_task()
            if answer == _BACK:
                step = 1
                continue
            task = answer
            step = 3

        elif step == 3:
            available = _scan_audio_files()
            if not available:
                console.print(
                    f"\n[yellow]No supported audio files found in "
                    f"{config.DEFAULT_INPUT_DIR}[/yellow]"
                )
                console.print("[cyan]Supported formats:[/cyan] "
                              + ", ".join(config.FILE_EXTENSIONS))
                input("\nPress Enter to return to menu...")
                return None

            answer = _select_files(available)
            if answer == _BACK:
                step = 2
                continue
            files = answer
            step = 4

        elif step == 4:
            clear_screen()
            settings = {
                "language": language,
                "model_size": model_size,
                "task": task,
                "files": files,
            }

            if not _show_summary(settings):
                step = 0
                continue

            return settings
