# src/home.py

from importlib.metadata import PackageNotFoundError, version

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src import config
from src.ui import clear_screen, format_size

console = Console()

try:
    _VERSION = version("whisper-transcriber")
except PackageNotFoundError:
    _VERSION = "unknown"

_DOC_SUFFIXES = (".md", ".srt", ".vtt", ".json")


def _render_header() -> str:
    title = f"Whisper Transcriber v{_VERSION}"
    width = len(title) + 6
    top = f"╭{'─' * width}╮"
    mid = f"│   {title}   │"
    bot = f"╰{'─' * width}╯"
    return f"{top}\n{mid}\n{bot}"


def _collect_stats() -> dict:
    audio_dir = config.DEFAULT_INPUT_DIR
    transcript_dir = config.DEFAULT_OUTPUT_DIR

    media_files = []
    for ext in config.MEDIA_EXTENSIONS:
        media_files.extend(audio_dir.glob(f"*{ext}"))
    media_files = sorted(set(media_files), key=lambda p: p.name.lower())

    all_txt = sorted(
        transcript_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    transcripts = [f for f in all_txt if not f.name.endswith("_summary.txt")]
    summaries = [f for f in all_txt if f.name.endswith("_summary.txt")]
    documents = [f for f in transcript_dir.iterdir()
                 if f.is_file() and f.suffix.lower() in _DOC_SUFFIXES]

    total_media = sum(f.stat().st_size for f in media_files) if media_files else 0

    return {
        "media_count": len(media_files),
        "transcript_count": len(transcripts),
        "summary_count": len(summaries),
        "document_count": len(documents),
        "total_media_size": format_size(total_media),
        "recent_transcripts": [f.stem for f in transcripts[:5]],
    }


def _render_stats(stats: dict, llm_available: bool) -> None:
    counts = Table(show_header=False, box=None, padding=(0, 2))
    counts.add_column(style="cyan")
    counts.add_column(style="green")
    counts.add_row("Audio library", f"{stats['media_count']} ({stats['total_media_size']})")
    counts.add_row("Transcripts", str(stats["transcript_count"]))
    counts.add_row("Documents", str(stats["document_count"]))
    counts.add_row("Summaries", str(stats["summary_count"]))
    counts.add_row(
        "Gemini",
        "[green]ready[/green]" if llm_available else "[dim]no API key[/dim]",
    )

    console.print(Panel(counts, title="[bold]Stats[/bold]", border_style="dim", expand=False))

    if stats["recent_transcripts"]:
        recent = ", ".join(stats["recent_transcripts"][:3])
        if len(stats["recent_transcripts"]) > 3:
            recent += f" +{len(stats['recent_transcripts']) - 3} more"
        console.print(f"  [dim]Recent:[/dim] {recent}")
    console.print()


def show_home(llm_available: bool = False) -> str | None:
    """Display the home screen and return the user's menu choice."""
    clear_screen()
    console.print()
    console.print(f"[bold cyan]{_render_header()}[/bold cyan]")
    console.print()

    _render_stats(_collect_stats(), llm_available)

    choices = [
        questionary.Choice("Transcribe          audio or video, from anywhere", value="Transcribe"),
        questionary.Choice(
            "Summarize           an existing transcript",
            value="Summarize",
            disabled=None if llm_available else "needs GEMINI_API_KEY",
        ),
        questionary.Choice("Manage Files", value="Manage Files"),
        questionary.Choice("Settings", value="Settings"),
        questionary.Separator(),
        questionary.Choice("Exit", value="Exit"),
    ]

    answer = questionary.select(
        "What would you like to do?", choices=choices, instruction="",
    ).ask()

    if answer is None:
        raise KeyboardInterrupt

    return answer
