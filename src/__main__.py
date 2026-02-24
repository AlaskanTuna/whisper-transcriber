# src/__main__.py

from rich.console import Console
from rich.spinner import Spinner
from rich.live import Live

from src.config import DEFAULT_INPUT_DIR, DEFAULT_OUTPUT_DIR
from src.ui import run_setup, clear_screen
from src.transcriber import load_model, process_directory

console = Console()


def _run_transcription(settings: dict) -> None:
    """
    Load model and process files from the given settings dict.
    """
    clear_screen()

    console.print()
    with Live(
        Spinner("dots", text=f"Loading model '{settings['model_size']}'..."),
        console=console,
    ):
        model = load_model(settings["model_size"])

    console.print(f"[green]Model '{settings['model_size']}' loaded.[/green]\n")

    count = process_directory(
        model=model,
        input_dir=settings["input_dir"],
        output_dir=settings["output_dir"],
        language=settings["language"],
        task=settings["task"],
        file_extension=settings["file_extension"],
    )

    console.print()
    if count:
        console.print(
            f"[bold green]Done — {count} file(s) transcribed.[/bold green]"
        )
        console.print(f"Output directory: {settings['output_dir']}")
    else:
        console.print(
            f"[yellow]No '{settings['file_extension']}' files found "
            f"in {settings['input_dir']}[/yellow]"
        )


def main() -> None:
    """
    Runs TUI setup then transcription. 
    Returns to menu on completion or error.
    """
    DEFAULT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            clear_screen()
            settings = run_setup()
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
