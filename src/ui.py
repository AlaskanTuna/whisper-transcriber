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


def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def _step_header(step_num: int, total: int, name: str) -> None:
    console.print(f"\n[dim]Step {step_num}/{total} \u2014 {name}[/dim]")


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


def _format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} B"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


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


def _select_task(summarize_available: bool) -> str:
    task_list = config.TASKS + config.SUMMARY_TASKS if summarize_available else config.TASKS
    choices = task_list + [
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


def _select_summary_style() -> str:
    choices = config.SUMMARY_STYLES + [
        questionary.Choice(title=_BACK_LABEL, value=_BACK),
        questionary.Choice(title=_EXIT_LABEL, value=_EXIT),
    ]
    answer = questionary.select(
        "Select summary style:",
        choices=choices,
        default=config.DEFAULT_SUMMARY_STYLE,
        instruction="",
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    return answer


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
    if settings.get("summary_style"):
        table.add_row("Summary Style", settings["summary_style"])
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


def _build_steps(has_summary_style: bool) -> list[str]:
    """Build dynamic step name list based on active features."""
    steps = ["Language", "Model", "Task"]
    if has_summary_style:
        steps.append("Summary Style")
    steps.extend(["Files", "Confirm"])
    return steps


def run_setup(summarize_available: bool = False) -> dict | None:
    # Steps are: Language(0), Model(1), Task(2), [SummaryStyle(3)], Files, Confirm
    # We use named states instead of fragile indices for the conditional step.
    state = "language"
    language: Optional[str] = None
    model_size: str = ""
    task: str = ""
    summary_style: Optional[str] = None
    files: list[Path] = []

    def _needs_summary_style() -> bool:
        return "summarize" in task

    def _header(name: str) -> None:
        steps = _build_steps(_needs_summary_style())
        idx = steps.index(name) + 1
        _step_header(idx, len(steps), name)

    while True:
        if state == "language":
            clear_screen()
            console.print("\n[bold cyan]=== Whisper Transcriber ===[/bold cyan]")
            _header("Language")
            answer = _select_language()
            if answer == _EXIT:
                return None
            language = None if answer == config.AUTO_DETECT else config.LANGUAGE_MAP[answer]
            state = "model"

        elif state == "model":
            _header("Model")
            _show_context(language, "", "")
            answer = _select_model_size()
            if answer == _BACK:
                state = "language"
                continue
            if answer == _EXIT:
                return None
            model_size = answer
            state = "task"

        elif state == "task":
            _header("Task")
            _show_context(language, model_size, "")
            answer = _select_task(summarize_available)
            if answer == _BACK:
                state = "model"
                continue
            if answer == _EXIT:
                return None
            task = answer
            state = "summary_style" if _needs_summary_style() else "files"

        elif state == "summary_style":
            _header("Summary Style")
            _show_context(language, model_size, task)
            answer = _select_summary_style()
            if answer == _BACK:
                state = "task"
                continue
            if answer == _EXIT:
                return None
            summary_style = config.SUMMARY_STYLE_MAP[answer]
            state = "files"

        elif state == "files":
            _header("Files")
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
                state = "summary_style" if _needs_summary_style() else "task"
                continue

            answer = _select_files(available)
            if answer == _BACK:
                state = "summary_style" if _needs_summary_style() else "task"
                continue
            if answer == _EXIT:
                return None
            files = answer
            state = "confirm"

        elif state == "confirm":
            clear_screen()
            _header("Confirm")
            _show_context(language, model_size, task)
            settings = {
                "language": language,
                "model_size": model_size,
                "task": task,
                "summary_style": summary_style,
                "files": files,
            }

            if not _show_summary(settings):
                state = "files"
                continue

            return settings
