# src/home.py

from pathlib import Path

import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src import config
from src.ui import clear_screen, format_size

console = Console()

_VERSION = "0.2.0"


def _render_header() -> str:
    title = f"Whisper Transcriber v{_VERSION}"
    width = len(title) + 6
    top = f"\u256d{'─' * width}\u256e"
    mid = f"\u2502   {title}   \u2502"
    bot = f"\u2570{'─' * width}\u256f"
    return f"{top}\n{mid}\n{bot}"


def _collect_stats() -> dict:
    audio_dir = config.DEFAULT_INPUT_DIR
    transcript_dir = config.DEFAULT_OUTPUT_DIR

    # Audio files
    audio_files = []
    for ext in config.FILE_EXTENSIONS:
        audio_files.extend(audio_dir.glob(f"*{ext}"))
    audio_files = sorted(set(audio_files), key=lambda p: p.name.lower())

    # Transcript files (exclude summaries)
    all_txt = sorted(transcript_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    transcripts = [f for f in all_txt if not f.name.endswith("_summary.txt")]
    summaries = [f for f in all_txt if f.name.endswith("_summary.txt")]

    # Sizes
    total_audio = sum(f.stat().st_size for f in audio_files) if audio_files else 0
    transcript_sizes = [f.stat().st_size for f in transcripts]
    avg_transcript = sum(transcript_sizes) // len(transcript_sizes) if transcript_sizes else 0

    return {
        "audio_count": len(audio_files),
        "transcript_count": len(transcripts),
        "summary_count": len(summaries),
        "total_audio_size": format_size(total_audio),
        "avg_transcript_size": format_size(avg_transcript),
        "recent_transcripts": [f.stem for f in transcripts[:5]],
        "recent_summaries": [f.stem.removesuffix("_summary") for f in summaries[:5]],
    }


def _render_stats(stats: dict) -> None:
    # Counts table
    counts = Table(show_header=False, box=None, padding=(0, 2))
    counts.add_column(style="cyan")
    counts.add_column(style="green")
    counts.add_row("Audio files", f"{stats['audio_count']} ({stats['total_audio_size']})")
    counts.add_row("Transcripts", str(stats["transcript_count"]))
    counts.add_row("Summaries", str(stats["summary_count"]))
    counts.add_row("Avg transcript", stats["avg_transcript_size"])

    console.print(Panel(counts, title="[bold]Stats[/bold]", border_style="dim", expand=False))

    # Recent files
    if stats["recent_transcripts"]:
        recent = ", ".join(stats["recent_transcripts"][:3])
        if len(stats["recent_transcripts"]) > 3:
            recent += f" +{len(stats['recent_transcripts']) - 3} more"
        console.print(f"  [dim]Recent:[/dim] {recent}")
    console.print()


def show_home() -> str | None:
    """Display the home screen and return the user's menu choice."""
    clear_screen()
    console.print()
    console.print(f"[bold cyan]{_render_header()}[/bold cyan]")
    console.print()

    stats = _collect_stats()
    _render_stats(stats)

    choices = [
        questionary.Choice("Start", value="Start"),
        questionary.Choice("Manage Files", value="Manage Files"),
        questionary.Choice("Settings", value="Settings"),
        questionary.Separator(),
        questionary.Choice("Exit", value="Exit"),
    ]

    answer = questionary.select(
        "What would you like to do?",
        choices=choices,
        instruction="",
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    return answer
