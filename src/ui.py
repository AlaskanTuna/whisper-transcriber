# src/ui.py

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

_STEP_NAMES = ["Language", "Model", "Task", "Files", "Confirm"]
_TOTAL_STEPS = len(_STEP_NAMES)


def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def _step_header(step: int) -> None:
    console.print(
        f"\n[dim]Step {step + 1}/{_TOTAL_STEPS} \u2014 {_STEP_NAMES[step]}[/dim]"
    )


def _show_context(
    language: Optional[str], model_size: str, task: str, past_language_step: bool = True
) -> None:
    parts = []
    if past_language_step:
        parts.append(f"Language: {language or 'Auto'}")
    if model_size:
        parts.append(f"Model: {model_size}")
    if task:
        parts.append(f"Task: {task}")
    if parts:
        console.print(f"[dim]{' | '.join(parts)}[/dim]")


def _scan_audio_files() -> list[Path]:
    files: list[Path] = []
    for ext in config.FILE_EXTENSIONS:
        files.extend(config.DEFAULT_INPUT_DIR.glob(f"*{ext}"))
    return sorted(set(files), key=lambda p: p.name.lower())


def _select_language() -> Optional[str]:
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
    choices = config.MODEL_SIZES + [
        questionary.Choice(title=_BACK_LABEL, value=_BACK),
        questionary.Choice(title=_EXIT_LABEL, value=_EXIT),
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
    choices = config.TASKS + [
        questionary.Choice(title=_BACK_LABEL, value=_BACK),
        questionary.Choice(title=_EXIT_LABEL, value=_EXIT),
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


def _format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} B"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _select_files(available: list[Path]) -> list[Path] | str:
    choices = []
    for f in available:
        size = _format_size(f.stat().st_size)
        has_transcript = (config.DEFAULT_OUTPUT_DIR / f"{f.stem}.txt").exists()
        label = f"{f.name} ({size})"
        if has_transcript:
            label += " [has transcript]"
        choices.append(questionary.Choice(label, value=str(f)))
    choices.append(questionary.Choice(title=_BACK_LABEL, value=_BACK))
    choices.append(questionary.Choice(title=_EXIT_LABEL, value=_EXIT))

    answer = questionary.checkbox(
        "Select audio files (space to toggle, enter to confirm):",
        choices=choices,
        instruction="",
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    if _EXIT in answer:
        return _EXIT

    if _BACK in answer:
        return _BACK

    if not answer:
        return _BACK

    return [Path(p) for p in answer if p not in (_BACK, _EXIT)]


def _show_summary(settings: dict) -> bool:
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
    step = 0
    language: Optional[str] = None
    model_size: str = ""
    task: str = ""
    files: list[Path] = []

    while True:
        if step == 0:
            clear_screen()
            console.print("\n[bold cyan]=== Whisper Transcriber ===[/bold cyan]")
            _step_header(0)
            answer = _select_language()
            if answer == _EXIT:
                return None
            language = None if answer == config.AUTO_DETECT else config.LANGUAGE_MAP[answer]
            step = 1

        elif step == 1:
            _step_header(1)
            _show_context(language, "", "")
            answer = _select_model_size()
            if answer == _BACK:
                step = 0
                continue
            if answer == _EXIT:
                return None
            model_size = answer
            step = 2

        elif step == 2:
            _step_header(2)
            _show_context(language, model_size, "")
            answer = _select_task()
            if answer == _BACK:
                step = 1
                continue
            if answer == _EXIT:
                return None
            task = answer
            step = 3

        elif step == 3:
            _step_header(3)
            _show_context(language, model_size, task)
            available = _scan_audio_files()
            if not available:
                console.print(
                    f"\n[yellow]No supported audio files found in "
                    f"{config.DEFAULT_INPUT_DIR}[/yellow]"
                )
                console.print(
                    "[cyan]Supported formats:[/cyan] "
                    + ", ".join(config.FILE_EXTENSIONS)
                )
                input("\nPress Enter to go back...")
                step = 2
                continue

            answer = _select_files(available)
            if answer == _BACK:
                step = 2
                continue
            if answer == _EXIT:
                return None
            files = answer
            step = 4

        elif step == 4:
            clear_screen()
            _step_header(4)
            _show_context(language, model_size, task)
            settings = {
                "language": language,
                "model_size": model_size,
                "task": task,
                "files": files,
            }

            if not _show_summary(settings):
                step = 3
                continue

            return settings
