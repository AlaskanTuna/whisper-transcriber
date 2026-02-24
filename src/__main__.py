# src/__main__.py

from rich.console import Console
from rich.spinner import Spinner
from rich.live import Live
from rich.table import Table

from src.config import DEFAULT_INPUT_DIR, DEFAULT_OUTPUT_DIR
from src.ui import run_setup, clear_screen
from src.transcriber import load_model, process_queue

console = Console()


def _show_results(results: list[dict]) -> None:
    """
    Display an operation summary table after queue processing.

    @results: List of dicts with keys 'file' (str) and 'success' (bool).
    """
    table = Table(title="Operation Summary")
    table.add_column("File", style="cyan")
    table.add_column("Status", style="green")

    succeeded = 0
    failed = 0

    for r in results:
        if r["success"]:
            table.add_row(r["file"], "[green]Success[/green]")
            succeeded += 1
        else:
            table.add_row(r["file"], "[red]Failed[/red]")
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
    clear_screen()

    console.print()
    with Live(
        Spinner("dots", text=f"Loading model '{settings['model_size']}'..."),
        console=console,
    ):
        model = load_model(settings["model_size"])

    console.print(f"[green]Model '{settings['model_size']}' loaded.[/green]\n")

    results = process_queue(
        model=model,
        files=settings["files"],
        output_dir=DEFAULT_OUTPUT_DIR,
        language=settings["language"],
        task=settings["task"],
    )

    _show_results(results)


def main() -> None:
    """
    Main loop — runs TUI setup then transcription.
    Returns to menu on completion or error.
    """
    DEFAULT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            clear_screen()
            settings = run_setup()

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
