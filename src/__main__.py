# src/__main__.py

"""
Entry point.

With arguments, this is a headless CLI. Without them, it opens the TUI. Both
paths run the same pipeline.
"""

import sys
import time

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table

from src import config
from src.home import show_home
from src.llm import is_available as llm_available
from src.llm import load_env
from src.pipeline import JobOptions, JobResult, run_jobs
from src.ui import clear_screen, run_setup, select_transcripts_to_summarize

console = Console()


def _show_results(results: list[JobResult]) -> None:
    """Print a per-file summary with the full path of everything written."""
    table = Table(title="Results")
    table.add_column("File", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Written", style="green", justify="right")

    for r in results:
        if r.success:
            table.add_row(r.source.name, "[green]Done[/green]", str(len(r.outputs)))
        else:
            table.add_row(r.source.name, f"[red]Failed: {r.error}[/red]", "0")

    console.print()
    console.print(table)

    for r in results:
        if not r.outputs and not r.skipped and not r.warnings:
            continue
        console.print(f"\n[bold]{r.source.name}[/bold]")
        for path in r.outputs:
            console.print(f"  [cyan]{path}[/cyan]", soft_wrap=True)
        for path in r.skipped:
            console.print(
                f"  [yellow]skipped, already exists:[/yellow] {path}", soft_wrap=True
            )
        for warning in r.warnings:
            console.print(f"  [yellow]warning:[/yellow] {warning}")

    succeeded = sum(1 for r in results if r.success)
    console.print(
        f"\n[bold]{succeeded} succeeded, {len(results) - succeeded} failed "
        f"out of {len(results)}[/bold]"
    )


def _run_transcription(settings: dict) -> None:
    """Run the pipeline for a TUI-configured job."""
    clear_screen()

    opts = JobOptions(
        model_size=settings["model_size"],
        language=settings["language"],
        task=settings["task"],
        formats=settings["formats"],
        output=settings["output"],
        polish_profile=settings["polish_profile"],
        context=settings["context"],
        summarize=settings["summarize"],
        summary_style=settings["summary_style"],
        overwrite=settings["overwrite"],
    )

    start = time.monotonic()
    spinner = Spinner("dots", text="Starting…")
    live = Live(spinner, console=console, refresh_per_second=10)

    def on_progress(stage: str, message: str) -> None:
        # Whisper's own bar carries an ETA; let it have the terminal.
        if stage == "transcribe":
            live.stop()
            console.print(f"[cyan]{message}[/cyan]")
        else:
            live.start()
            spinner.update(text=message)

    def on_model_load(size: str) -> None:
        live.start()
        spinner.update(text=f"Loading model '{size}'…")

    try:
        results = run_jobs(settings["sources"], opts, on_progress, on_model_load)
    finally:
        live.stop()

    minutes, seconds = divmod(int(time.monotonic() - start), 60)
    elapsed = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
    console.print(f"[dim]Completed in {elapsed}[/dim]")

    _show_results(results)


def _run_standalone_summarization(settings: dict) -> None:
    """Summarize existing transcript files without running Whisper."""
    from src.summarizer import summarize_file  # pylint: disable=import-outside-toplevel

    clear_screen()
    console.print()

    table = Table(title="Summary Results")
    table.add_column("File", style="cyan")
    table.add_column("Status", style="green")

    succeeded = 0
    for path in settings["transcript_files"]:
        summary_path = path.parent / f"{path.stem}_summary.txt"
        with Live(Spinner("dots", text=f"Summarizing {path.name}…"), console=console):
            success, error = summarize_file(path, summary_path, settings["summary_style"])
        if success:
            table.add_row(path.name, f"[green]{summary_path}[/green]")
            succeeded += 1
        else:
            table.add_row(path.name, f"[red]Failed: {error}[/red]")

    console.print()
    console.print(table)
    console.print(
        f"\n[bold]{succeeded} succeeded, "
        f"{len(settings['transcript_files']) - succeeded} failed[/bold]"
    )


def run_tui() -> None:
    """Home page loop."""
    config.DEFAULT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    config.DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    load_env()
    has_llm = llm_available()

    while True:
        try:
            choice = show_home(llm_available=has_llm)

            if choice in (None, "Exit"):
                break

            if choice == "Transcribe":
                settings = run_setup(llm_available=has_llm)
                if settings is None:
                    continue
                _run_transcription(settings)
                console.print()
                input("Press Enter to return to menu...")

            elif choice == "Summarize":
                settings = select_transcripts_to_summarize()
                if settings is None:
                    continue
                _run_standalone_summarization(settings)
                console.print()
                input("Press Enter to return to menu...")

            elif choice == "Manage Files":
                from src.files import run_manage_files  # pylint: disable=import-outside-toplevel
                run_manage_files()

            elif choice == "Settings":
                from src.settings import run_settings  # pylint: disable=import-outside-toplevel
                run_settings()

        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled.[/yellow]")
            break
        except SystemExit:
            raise
        except Exception as e:  # pylint: disable=broad-exception-caught
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            console.print("[cyan]Returning to menu...[/cyan]\n")
            input("Press Enter to continue...")


def main() -> None:
    """Dispatch to the headless CLI when arguments are given, otherwise the TUI."""
    if len(sys.argv) > 1:
        from src.cli import main as cli_main  # pylint: disable=import-outside-toplevel
        sys.exit(cli_main())
    run_tui()


if __name__ == "__main__":
    main()
