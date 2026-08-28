# src/ui.py

"""
Interactive setup.

Two questions get you running -- where the recording is, and which file -- then
a summary screen you either accept or drill into. Settings default to config.yaml
so a repeat run is two keystrokes.
"""

from pathlib import Path
from typing import Optional

import questionary
from rich.console import Console
from rich.table import Table

from src import config, paths

console = Console()

_BACK = "BACK"
_EXIT = "EXIT"
_BACK_LABEL = [("bold", "BACK")]
_EXIT_LABEL = [("bold", "EXIT")]

_FORMAT_HELP = {
    "txt": "timestamped transcript",
    "md": "structured document, written by Gemini",
    "srt": "subtitles",
    "vtt": "subtitles, web",
    "json": "segments with timings",
}

_PROFILE_HELP = {
    "meeting": "speakers, decisions, figures, open items",
    "talk": "topic sections, claims, takeaways",
    "general": "topic sections, neutral",
}


def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} B"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _ask(prompt) -> object:
    """Run a questionary prompt, turning Ctrl-C into KeyboardInterrupt."""
    answer = prompt.ask()
    if answer is None:
        raise KeyboardInterrupt
    return answer


def _scan_media_files() -> list[Path]:
    """List media files sitting in the project's audio library."""
    files: list[Path] = []
    for ext in config.MEDIA_EXTENSIONS:
        files.extend(config.DEFAULT_INPUT_DIR.glob(f"*{ext}"))
    return sorted(set(files), key=lambda p: p.name.lower())


def scan_transcript_files() -> list[Path]:
    """Scan transcripts/ for .txt files, excluding *_summary.txt."""
    all_txt = list(config.DEFAULT_OUTPUT_DIR.glob("*.txt"))
    return sorted(
        [f for f in all_txt if not f.name.endswith("_summary.txt")],
        key=lambda p: p.name.lower(),
    )


# ─── Source selection ────────────────────────────────────────────────────────

def _select_from_library() -> list[Path] | str:
    """Pick one or more files from the project's audio library."""
    available = _scan_media_files()
    if not available:
        console.print(
            f"\n[yellow]No media files in {config.DEFAULT_INPUT_DIR}[/yellow]\n"
            f"[dim]Supported: {', '.join(config.MEDIA_EXTENSIONS)}[/dim]"
        )
        input("\nPress Enter to go back...")
        return _BACK

    choices = []
    for f in available:
        label = f"{f.name} ({format_size(f.stat().st_size)})"
        if (config.DEFAULT_OUTPUT_DIR / f"{f.stem}.txt").exists():
            label += " [has transcript]"
        choices.append(questionary.Choice(label, value=str(f)))
    choices.append(questionary.Choice(title=_BACK_LABEL, value=_BACK))

    answer = _ask(questionary.checkbox(
        "Select files (space to toggle, enter to confirm):",
        choices=choices,
        instruction="",
    ))
    if _BACK in answer or not answer:
        return _BACK
    return [Path(p) for p in answer if p != _BACK]


def _select_by_path() -> list[Path] | str:
    """Type or tab-complete a path to any file or folder on disk."""
    console.print(
        "\n[dim]Any audio or video file, or a folder of them. Tab completes paths.[/dim]"
    )
    answer = _ask(questionary.path("File or folder:", only_directories=False))
    raw = str(answer).strip()
    if not raw:
        return _BACK

    candidate = Path(raw).expanduser()
    if not candidate.exists():
        console.print(f"\n[red]Not found:[/red] {candidate}")
        input("\nPress Enter to try again...")
        return _BACK

    found = paths.collect_media([candidate])
    if not found:
        console.print(f"\n[red]No supported media found in:[/red] {candidate}")
        console.print(f"[dim]Supported: {', '.join(config.MEDIA_EXTENSIONS)}[/dim]")
        input("\nPress Enter to try again...")
        return _BACK

    if len(found) > 1:
        console.print(f"\n[green]Found {len(found)} media files.[/green]")
    return found


def _select_sources() -> list[Path] | str:
    """Ask where the recording lives, then collect the files."""
    library_count = len(_scan_media_files())
    choices = [
        questionary.Choice(
            "Enter a file or folder path…    [any location, tab-completes]",
            value="path",
        ),
        questionary.Choice(
            f"Pick from the audio library     [{library_count} file(s) in audio/]",
            value="library",
        ),
        questionary.Separator(),
        questionary.Choice(title=_EXIT_LABEL, value=_EXIT),
    ]
    answer = _ask(questionary.select(
        "Where is the recording?", choices=choices, instruction="",
    ))
    if answer == _EXIT:
        return _EXIT
    return _select_by_path() if answer == "path" else _select_from_library()


# ─── Settings editing ────────────────────────────────────────────────────────

def _edit_language(current: Optional[str]) -> Optional[str]:
    choices = [config.AUTO_DETECT] + config.LANGUAGES
    default = config.AUTO_DETECT
    if current:
        default = next((l for l in config.LANGUAGES if l.lower() == current), config.AUTO_DETECT)
    answer = _ask(questionary.select(
        "Language:", choices=choices, default=default, instruction="",
    ))
    return None if answer == config.AUTO_DETECT else config.LANGUAGE_MAP[answer]


def _edit_model(current: str) -> str:
    return str(_ask(questionary.select(
        "Model size:", choices=config.MODEL_SIZES, default=current, instruction="",
    )))


def _edit_task(current: str) -> str:
    return str(_ask(questionary.select(
        "Task:", choices=config.TASKS, default=current, instruction="",
    )))


def _edit_formats(current: list[str], llm_available: bool) -> list[str]:
    choices = []
    for fmt in config.OUTPUT_FORMATS:
        needs_key = fmt == config.POLISHED_FORMAT and not llm_available
        label = f"{fmt:<5} {_FORMAT_HELP[fmt]}"
        choices.append(questionary.Choice(
            label,
            value=fmt,
            checked=fmt in current and not needs_key,
            disabled="needs GEMINI_API_KEY" if needs_key else None,
        ))
    answer = _ask(questionary.checkbox(
        "Output formats (space to toggle):", choices=choices, instruction="",
    ))
    picked = list(answer) or [config.DEFAULT_OUTPUT_FORMAT]
    if config.POLISHED_FORMAT in picked and "txt" not in picked:
        picked.insert(0, "txt")
    return [f for f in config.OUTPUT_FORMATS if f in picked]


def _edit_profile(current: str) -> str:
    choices = [
        questionary.Choice(f"{p:<9} {_PROFILE_HELP[p]}", value=p)
        for p in config.POLISH_PROFILES
    ]
    return str(_ask(questionary.select(
        "Document profile:", choices=choices, default=None, instruction="",
    )) or current)


def _edit_context(current: Optional[str]) -> Optional[str]:
    console.print(
        "\n[dim]Names, companies and spellings the recogniser will get wrong.\n"
        "Example: \"Alex Toh of TDG Group; Anderson and Zijie of NexTalent\"[/dim]"
    )
    answer = str(_ask(questionary.text("Known names and context:", default=current or ""))).strip()
    return answer or None


def _edit_output(current: Optional[Path], sources: list[Path]) -> Optional[Path]:
    beside = paths.plan_output(sources[0], None).directory if sources else Path.cwd()
    choices = [
        questionary.Choice(f"Beside the input file        [{beside}]", value="beside"),
        questionary.Choice(
            f"Project transcripts/ folder  [{config.DEFAULT_OUTPUT_DIR}]", value="project",
        ),
        questionary.Choice("Choose another folder…", value="custom"),
    ]
    answer = _ask(questionary.select(
        "Where should the results go?", choices=choices, instruction="",
    ))
    if answer == "beside":
        return None
    if answer == "project":
        return config.DEFAULT_OUTPUT_DIR
    chosen = str(_ask(questionary.path("Folder:", only_directories=True))).strip()
    return Path(chosen).expanduser() if chosen else current


def _change_settings(settings: dict, llm_available: bool) -> None:
    """Loop over the individual settings until the user goes back."""
    while True:
        clear_screen()
        console.print("\n[bold cyan]Settings for this run[/bold cyan]\n")
        formats = ", ".join(settings["formats"])
        polished = config.POLISHED_FORMAT in settings["formats"]
        rows = [
            ("model", f"Model size: {settings['model_size']}"),
            ("language", f"Language: {settings['language'] or 'Auto (detect)'}"),
            ("task", f"Task: {settings['task']}"),
            ("formats", f"Output formats: {formats}"),
            ("output", f"Destination: {settings['output'] or 'beside the input file'}"),
        ]
        if polished:
            rows.append(("profile", f"Document profile: {settings['polish_profile']}"))
            rows.append(("context", f"Known names: {settings['context'] or '(none)'}"))
        if llm_available:
            rows.append(("summarize", f"Also write a summary: {'yes' if settings['summarize'] else 'no'}"))
        rows.append(("overwrite", f"Overwrite existing files: {'yes' if settings['overwrite'] else 'no'}"))

        choices = [questionary.Choice(label, value=key) for key, label in rows]
        choices += [questionary.Separator(), questionary.Choice("Done", value=_BACK)]

        answer = _ask(questionary.select("Change:", choices=choices, instruction=""))
        if answer == _BACK:
            return

        if answer == "model":
            settings["model_size"] = _edit_model(settings["model_size"])
        elif answer == "language":
            settings["language"] = _edit_language(settings["language"])
        elif answer == "task":
            settings["task"] = _edit_task(settings["task"])
        elif answer == "formats":
            settings["formats"] = _edit_formats(settings["formats"], llm_available)
        elif answer == "output":
            settings["output"] = _edit_output(settings["output"], settings["sources"])
        elif answer == "profile":
            settings["polish_profile"] = _edit_profile(settings["polish_profile"])
        elif answer == "context":
            settings["context"] = _edit_context(settings["context"])
        elif answer == "summarize":
            settings["summarize"] = not settings["summarize"]
        elif answer == "overwrite":
            settings["overwrite"] = not settings["overwrite"]


# ─── Summary screen ──────────────────────────────────────────────────────────

def _show_plan(settings: dict) -> None:
    """Print what is about to happen, including every output path."""
    sources = settings["sources"]

    table = Table(title="Ready to transcribe", show_lines=False)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Files", f"{len(sources)}: " + ", ".join(s.name for s in sources[:3])
                  + (f" +{len(sources) - 3} more" if len(sources) > 3 else ""))
    table.add_row("Model", settings["model_size"])
    table.add_row("Language", settings["language"] or "Auto (detect)")
    table.add_row("Task", settings["task"])
    table.add_row("Formats", ", ".join(settings["formats"]))
    if config.POLISHED_FORMAT in settings["formats"]:
        table.add_row("Document profile", settings["polish_profile"])
        if settings["context"]:
            table.add_row("Known names", settings["context"][:60])
    if settings["summarize"]:
        table.add_row("Summary", settings["summary_style"])

    console.print()
    console.print(table)

    plan = paths.plan_output(sources[0], settings["output"])
    console.print(f"\n[bold]Writing to[/bold] [cyan]{plan.directory}[/cyan]")
    for fmt in settings["formats"]:
        console.print(f"  {plan.path_for(fmt).name}")
    if len(sources) > 1:
        console.print(f"  [dim]... and the same for {len(sources) - 1} more file(s)[/dim]")
    console.print()


def run_setup(llm_available: bool = False) -> dict | None:
    """
    Collect everything needed for a run.

    @llm_available: Whether GEMINI_API_KEY is set, gating the Markdown and summary options.
    @return: A settings dict, or None if the user backed out.
    """
    default_formats = [config.DEFAULT_OUTPUT_FORMAT]
    if config.DEFAULT_POLISH and llm_available:
        default_formats = ["txt", config.POLISHED_FORMAT]

    settings: dict = {
        "sources": [],
        "model_size": config.DEFAULT_MODEL_SIZE,
        "language": None if config.DEFAULT_LANGUAGE == config.AUTO_DETECT
        else config.LANGUAGE_MAP.get(config.DEFAULT_LANGUAGE, config.DEFAULT_LANGUAGE),
        "task": config.DEFAULT_TASK,
        "formats": default_formats,
        "output": None,
        "polish_profile": config.DEFAULT_POLISH_PROFILE,
        "context": None,
        "summarize": False,
        "summary_style": config.SUMMARY_STYLE_MAP[config.DEFAULT_SUMMARY_STYLE],
        "overwrite": False,
    }

    while True:
        clear_screen()
        console.print("\n[bold cyan]=== Whisper Transcriber ===[/bold cyan]")
        chosen = _select_sources()
        if chosen == _EXIT:
            return None
        if chosen == _BACK:
            continue
        settings["sources"] = chosen
        break

    while True:
        clear_screen()
        _show_plan(settings)

        answer = _ask(questionary.select(
            "Proceed?",
            choices=[
                questionary.Choice("Start transcription", value="go"),
                questionary.Choice("Change settings…", value="settings"),
                questionary.Separator(),
                questionary.Choice(title=_BACK_LABEL, value=_BACK),
            ],
            instruction="",
        ))

        if answer == "go":
            return settings
        if answer == _BACK:
            return None
        _change_settings(settings, llm_available)


# ─── Standalone summarization ────────────────────────────────────────────────

def select_transcripts_to_summarize() -> dict | None:
    """Pick existing transcripts and a style for the summarize-only flow."""
    available = scan_transcript_files()
    if not available:
        console.print(f"\n[yellow]No transcripts in {config.DEFAULT_OUTPUT_DIR}[/yellow]")
        input("\nPress Enter to go back...")
        return None

    choices = []
    for f in available:
        label = f"{f.name} ({format_size(f.stat().st_size)})"
        if (f.parent / f"{f.stem}_summary.txt").exists():
            label += " [has summary]"
        choices.append(questionary.Choice(label, value=str(f)))
    choices.append(questionary.Choice(title=_BACK_LABEL, value=_BACK))

    answer = _ask(questionary.checkbox(
        "Select transcripts (space to toggle, enter to confirm):",
        choices=choices,
        instruction="",
    ))
    if _BACK in answer or not answer:
        return None

    style = _ask(questionary.select(
        "Summary style:",
        choices=config.SUMMARY_STYLES,
        default=config.DEFAULT_SUMMARY_STYLE,
        instruction="",
    ))
    return {
        "transcript_files": [Path(p) for p in answer if p != _BACK],
        "summary_style": config.SUMMARY_STYLE_MAP[str(style)],
    }
