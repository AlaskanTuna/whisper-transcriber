# src/__main__.py

import time

from rich.console import Console
from rich.spinner import Spinner
from rich.live import Live
from rich.table import Table

from src import config
from src.config import DEFAULT_INPUT_DIR, DEFAULT_OUTPUT_DIR
from src.ui import run_setup, clear_screen
from src.summarizer import load_env, is_available as summarize_available

console = Console()


def _show_results(results: list[dict]) -> None:
    """
    Display an operation summary table after queue processing.

    @results: List of dicts with keys 'file', 'success', and 'error'.
    """
    has_summaries = any("summary_success" in r for r in results)

    table = Table(title="Operation Summary")
    table.add_column("File", style="cyan")
    table.add_column("Transcription", style="green")
    if has_summaries:
        table.add_column("Summary", style="green")

    succeeded = 0
    failed = 0

    for r in results:
        t_status = "[green]Success[/green]" if r["success"] else (
            f"[red]Failed: {r['error']}[/red]" if r.get("error") else "[red]Failed[/red]"
        )

        if has_summaries:
            if "summary_success" not in r:
                s_status = "[dim]-[/dim]"
            elif r["summary_success"]:
                s_status = "[green]Done[/green]"
            else:
                s_status = f"[red]Failed: {r.get('summary_error', '')}[/red]"
            table.add_row(r["file"], t_status, s_status)
        else:
            table.add_row(r["file"], t_status)

        if r["success"]:
            succeeded += 1
        else:
            failed += 1

    console.print()
    console.print(table)
    console.print()
    console.print(
        f"[bold]{succeeded} succeeded, {failed} failed "
        f"out of {len(results)}[/bold]"
    )
    console.print(f"Output directory: {DEFAULT_OUTPUT_DIR}")


def _run_transcription(settings: dict) -> None:
    """
    Load model and process the selected file queue.

    @settings: Config dict from run_setup().
    """
    from src.transcriber import load_model, process_queue, get_device

    clear_screen()

    console.print()
    with Live(
        Spinner("dots", text=f"Loading model '{settings['model_size']}'..."),
        console=console,
    ):
        model = load_model(settings["model_size"])

    device = get_device()
    console.print(f"[green]Model '{settings['model_size']}' loaded on {device}.[/green]\n")

    whisper_task = config.get_whisper_task(settings["task"])

    start_time = time.monotonic()

    results = process_queue(
        model=model,
        files=settings["files"],
        output_dir=DEFAULT_OUTPUT_DIR,
        language=settings["language"],
        task=whisper_task,
    )

    elapsed = time.monotonic() - start_time
    minutes, seconds = divmod(int(elapsed), 60)
    if minutes:
        console.print(f"[dim]Completed in {minutes}m {seconds}s[/dim]")
    else:
        console.print(f"[dim]Completed in {seconds}s[/dim]")

    # Summarize if requested
    if "summarize" in settings["task"] and results:
        _run_summarization(results, settings["summary_style"])

    _show_results(results)


def _run_summarization(results: list[dict], style: str) -> None:
    """Run Gemini summarization on successful transcripts."""
    from src.summarizer import summarize_file
    from pathlib import Path
    from rich.progress import Progress, SpinnerColumn, TextColumn, MofNCompleteColumn

    to_summarize = [r for r in results if r["success"]]
    if not to_summarize:
        return

    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        MofNCompleteColumn(),
        TextColumn("{task.fields[filename]}"),
    ) as progress:
        task_id = progress.add_task(
            "Summarizing", total=len(to_summarize), filename=""
        )

        for r in to_summarize:
            stem = Path(r["file"]).stem
            transcript_path = DEFAULT_OUTPUT_DIR / f"{stem}.txt"
            summary_path = DEFAULT_OUTPUT_DIR / f"{stem}_summary.txt"
            progress.update(task_id, filename=r["file"])
            success, error = summarize_file(transcript_path, summary_path, style)
            r["summary_success"] = success
            r["summary_error"] = error
            progress.advance(task_id)


def main() -> None:
    """
    Main loop -- runs TUI setup then transcription.
    Returns to menu on completion or error.
    """
    DEFAULT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    load_env()
    has_summarize = summarize_available()

    while True:
        try:
            clear_screen()
            settings = run_setup(summarize_available=has_summarize)

            if settings is None:
                break

            _run_transcription(settings)
            console.print()
            input("Press Enter to return to menu...")
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled.[/yellow]")
            break
        except SystemExit:
            raise
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            console.print("[cyan]Returning to menu...[/cyan]\n")
            input("Press Enter to continue...")


if __name__ == "__main__":
    main()
