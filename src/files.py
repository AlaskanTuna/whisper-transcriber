# src/files.py

import os
import subprocess
from pathlib import Path

import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src import config
from src.ui import clear_screen, format_size

console = Console()

_BACK = "BACK"
_BACK_LABEL = [("bold", "BACK")]


def _scan_all_files() -> tuple[list[Path], list[Path]]:
    """Return (audio_files, transcript_files) from their respective directories."""
    audio_files = []
    for ext in config.FILE_EXTENSIONS:
        audio_files.extend(config.DEFAULT_INPUT_DIR.glob(f"*{ext}"))
    audio_files = sorted(set(audio_files), key=lambda p: p.name.lower())

    transcript_files = sorted(
        config.DEFAULT_OUTPUT_DIR.glob("*.txt"),
        key=lambda p: p.name.lower(),
    )

    return audio_files, transcript_files


def _show_file_listing(audio_files: list[Path], transcript_files: list[Path]) -> None:
    """Display a summary table of all files."""
    table = Table(title="Files Overview", show_lines=False)
    table.add_column("Directory", style="cyan")
    table.add_column("Count", style="green", justify="right")
    table.add_column("Total Size", style="green", justify="right")

    audio_size = sum(f.stat().st_size for f in audio_files) if audio_files else 0
    transcript_size = sum(f.stat().st_size for f in transcript_files) if transcript_files else 0

    table.add_row("audio/", str(len(audio_files)), format_size(audio_size))
    table.add_row("transcripts/", str(len(transcript_files)), format_size(transcript_size))

    console.print()
    console.print(table)
    console.print()


def _view_transcript() -> None:
    """Select and preview a transcript file, with option to open in editor."""
    transcripts = sorted(
        config.DEFAULT_OUTPUT_DIR.glob("*.txt"),
        key=lambda p: p.name.lower(),
    )

    if not transcripts:
        console.print("\n[yellow]No transcript files found.[/yellow]")
        input("\nPress Enter to go back...")
        return

    choices = [
        questionary.Choice(f"{f.name} ({format_size(f.stat().st_size)})", value=str(f))
        for f in transcripts
    ]
    choices.append(questionary.Choice(title=_BACK_LABEL, value=_BACK))

    answer = questionary.select(
        "Select a transcript to view:",
        choices=choices,
        instruction="",
    ).ask()

    if answer is None:
        raise KeyboardInterrupt
    if answer == _BACK:
        return

    filepath = Path(answer)
    lines = filepath.read_text(encoding="utf-8").splitlines()
    preview = "\n".join(lines[:20])
    if len(lines) > 20:
        preview += f"\n\n[dim]... {len(lines) - 20} more lines[/dim]"

    console.print()
    console.print(Panel(preview, title=f"[bold]{filepath.name}[/bold]", border_style="cyan"))
    console.print()

    action = questionary.select(
        "What next?",
        choices=["Open in editor", "Back"],
        instruction="",
    ).ask()

    if action == "Open in editor":
        editor = os.environ.get("EDITOR", "nano")
        try:
            subprocess.run([editor, str(filepath)], check=False)
        except FileNotFoundError:
            console.print(f"[red]Editor '{editor}' not found. Set $EDITOR to your preferred editor.[/red]")
            input("\nPress Enter to continue...")


def _delete_files() -> None:
    """Select and delete files from audio/ and/or transcripts/."""
    audio_files, transcript_files = _scan_all_files()

    if not audio_files and not transcript_files:
        console.print("\n[yellow]No files to delete.[/yellow]")
        input("\nPress Enter to go back...")
        return

    choices = []
    for f in audio_files:
        label = f"[audio] {f.name} ({format_size(f.stat().st_size)})"
        choices.append(questionary.Choice(label, value=str(f)))
    for f in transcript_files:
        label = f"[transcripts] {f.name} ({format_size(f.stat().st_size)})"
        choices.append(questionary.Choice(label, value=str(f)))
    choices.append(questionary.Choice(title=_BACK_LABEL, value=_BACK))

    answer = questionary.checkbox(
        "Select files to delete (space to toggle, enter to confirm):",
        choices=choices,
        instruction="",
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    if _BACK in answer or not answer:
        return

    to_delete = [Path(p) for p in answer if p != _BACK]
    console.print(f"\n[bold yellow]About to delete {len(to_delete)} file(s).[/bold yellow]")

    confirm = questionary.confirm("This cannot be undone. Proceed?", default=False).ask()
    if confirm is None:
        raise KeyboardInterrupt

    if not confirm:
        console.print("[dim]Cancelled.[/dim]")
        return

    deleted = 0
    for f in to_delete:
        try:
            f.unlink()
            deleted += 1
        except OSError as e:
            console.print(f"[red]Failed to delete {f.name}: {e}[/red]")

    console.print(f"[green]Deleted {deleted} file(s).[/green]")
    input("\nPress Enter to continue...")


def run_manage_files() -> None:
    """Main file management loop."""
    while True:
        clear_screen()
        audio_files, transcript_files = _scan_all_files()
        _show_file_listing(audio_files, transcript_files)

        choices = [
            "View transcript",
            "Delete file(s)",
            questionary.Separator(),
            questionary.Choice("Back", value="Back"),
        ]

        answer = questionary.select(
            "What would you like to do?",
            choices=choices,
            instruction="",
        ).ask()

        if answer is None:
            raise KeyboardInterrupt

        if answer == "Back":
            return
        elif answer == "View transcript":
            _view_transcript()
        elif answer == "Delete file(s)":
            _delete_files()
