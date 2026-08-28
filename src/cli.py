"""
Headless command-line interface.

`transcriber` with no arguments opens the TUI; with arguments it runs the same
pipeline without prompting, so it can be scripted or called from other tools.
"""

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from rich.console import Console

from src import config, paths
from src.pipeline import JobOptions, JobResult, run_jobs

console = Console()

try:
    _VERSION = version("whisper-transcriber")
except PackageNotFoundError:
    _VERSION = "unknown"

_EPILOG = """\
examples:
  transcriber meeting.mp4                     transcribe a video, transcript lands beside it
  transcriber talk.mp3 -f md --profile talk    structured Markdown document
  transcriber *.mp4 -o ~/notes -f txt,md,srt   several files, several formats, one folder
  transcriber call.mp4 -f md --context "Alex Toh of TDG Group; Anderson of NexTalent"
  transcriber                                  no arguments opens the interactive TUI

output goes next to the input file, unless the input came from the project's
audio/ folder (then transcripts/), or you pass -o.
"""


def build_parser() -> argparse.ArgumentParser:
    """Build the headless argument parser."""
    parser = argparse.ArgumentParser(
        prog="transcriber",
        description="Transcribe audio or video locally with OpenAI Whisper.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "inputs", nargs="*", type=Path,
        help="audio or video files, or directories to scan; omit to open the TUI",
    )
    parser.add_argument(
        "-o", "--output", type=Path, metavar="PATH",
        help="output file or directory (default: beside the input)",
    )
    parser.add_argument(
        "-f", "--format", action="append", metavar="FMT",
        help=f"output formats, comma-separated or repeated: "
             f"{', '.join(config.OUTPUT_FORMATS)}, all (default: {config.DEFAULT_OUTPUT_FORMAT})",
    )
    parser.add_argument(
        "-m", "--model", choices=config.MODEL_SIZES, default=config.DEFAULT_MODEL_SIZE,
        help=f"Whisper model size (default: {config.DEFAULT_MODEL_SIZE})",
    )
    parser.add_argument(
        "-l", "--language", metavar="LANG", default=None,
        help="language code or name; omit to auto-detect",
    )
    parser.add_argument(
        "--task", choices=config.TASKS, default=config.DEFAULT_TASK,
        help=f"transcribe or translate to English (default: {config.DEFAULT_TASK})",
    )
    parser.add_argument(
        "--polish", action="store_true",
        help="produce a structured Markdown document (implies -f md)",
    )
    parser.add_argument(
        "--profile", choices=config.POLISH_PROFILES, default=config.DEFAULT_POLISH_PROFILE,
        help=f"how to shape the polished document (default: {config.DEFAULT_POLISH_PROFILE})",
    )
    parser.add_argument(
        "--context", metavar="TEXT", default=None,
        help="known names, companies and spellings, to anchor proper nouns",
    )
    parser.add_argument(
        "--context-file", type=Path, metavar="PATH", default=None,
        help="read --context from a file",
    )
    parser.add_argument("--summarize", action="store_true", help="also write a summary file")
    parser.add_argument(
        "--summary-style", choices=list(config.SUMMARY_STYLE_MAP.values()), default="concise",
        help="summary style (default: concise)",
    )
    parser.add_argument(
        "--audio-bitrate", default=config.DEFAULT_AUDIO_BITRATE, metavar="RATE",
        help=f"bitrate for audio extracted from video (default: {config.DEFAULT_AUDIO_BITRATE})",
    )
    parser.add_argument(
        "--no-keep-audio", action="store_true",
        help="delete audio extracted from video instead of caching it in audio/",
    )
    parser.add_argument("--overwrite", action="store_true", help="overwrite existing outputs")
    parser.add_argument(
        "--dry-run", action="store_true", help="show what would be written, then stop",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="only report errors")
    parser.add_argument("--version", action="version", version=f"whisper-transcriber {_VERSION}")
    return parser


def parse_formats(values: list[str] | None, polish: bool) -> list[str]:
    """
    Normalise -f values into an ordered, de-duplicated format list.

    @values: Raw -f arguments, each possibly comma-separated.
    @polish: Whether --polish was given, which adds the Markdown format.
    @return: Validated format names.
    """
    requested: list[str] = []
    for value in values or []:
        requested.extend(part.strip().lower() for part in value.split(",") if part.strip())

    if "all" in requested:
        requested = list(config.OUTPUT_FORMATS)
    if not requested:
        requested = [config.DEFAULT_OUTPUT_FORMAT]
    if polish and config.POLISHED_FORMAT not in requested:
        requested.append(config.POLISHED_FORMAT)

    unknown = [f for f in requested if f not in config.OUTPUT_FORMATS]
    if unknown:
        raise ValueError(
            f"Unknown format(s): {', '.join(unknown)}. "
            f"Choose from: {', '.join(config.OUTPUT_FORMATS)}, all"
        )

    # A polished document is built from the raw transcript, so keep the txt too.
    if config.POLISHED_FORMAT in requested and "txt" not in requested:
        requested.insert(0, "txt")

    seen: set[str] = set()
    return [f for f in requested if not (f in seen or seen.add(f))]


def _resolve_context(args: argparse.Namespace) -> str | None:
    """Read --context, or its file, into a single string."""
    if args.context_file:
        if not args.context_file.exists():
            raise ValueError(f"Context file not found: {args.context_file}")
        return args.context_file.read_text(encoding="utf-8").strip()
    return args.context


def _report(results: list[JobResult], quiet: bool) -> int:
    """Print a per-file report and return the process exit code."""
    failed = [r for r in results if not r.success]

    for r in results:
        if not r.success:
            console.print(f"[red]FAILED[/red] {r.source.name}: {r.error}")
            continue
        if quiet:
            continue
        console.print(f"[green]OK[/green] {r.source.name}")
        for path in r.outputs:
            console.print(f"    [cyan]{path}[/cyan]", soft_wrap=True)
        for path in r.skipped:
            console.print(
                f"    [yellow]skipped, exists:[/yellow] {path}  [dim]--overwrite to replace[/dim]",
                soft_wrap=True,
            )
        for warning in r.warnings:
            console.print(f"    [yellow]warning:[/yellow] {warning}")

    if not quiet and results:
        console.print(
            f"\n[bold]{len(results) - len(failed)} succeeded, {len(failed)} failed "
            f"out of {len(results)}[/bold]"
        )
    return 1 if failed else 0


def run(args: argparse.Namespace) -> int:
    """Execute a parsed headless invocation and return an exit code."""
    sources = paths.collect_media(args.inputs)
    if not sources:
        console.print("[red]No media files found in the given paths.[/red]")
        return 1

    try:
        formats = parse_formats(args.format, args.polish)
        context = _resolve_context(args)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return 1

    wants_llm = config.POLISHED_FORMAT in formats or args.summarize
    if wants_llm:
        from src.llm import is_available, load_env  # pylint: disable=import-outside-toplevel

        load_env()
        if not is_available():
            console.print(
                "[red]GEMINI_API_KEY is not set[/red] -- needed for --polish/-f md and "
                "--summarize. Add it to .env or unset those options."
            )
            return 1

    opts = JobOptions(
        model_size=args.model,
        language=args.language,
        task=args.task,
        formats=formats,
        output=args.output,
        polish_profile=args.profile,
        context=context,
        summarize=args.summarize,
        summary_style=args.summary_style,
        overwrite=args.overwrite,
        keep_audio=not args.no_keep_audio,
        audio_bitrate=args.audio_bitrate,
    )

    if args.dry_run:
        console.print(f"[bold]Would transcribe {len(sources)} file(s) "
                      f"with model '{opts.model_size}':[/bold]")
        for source in sources:
            plan = paths.plan_output(source, opts.output)
            console.print(f"  [cyan]{source}[/cyan]")
            for fmt in formats:
                console.print(f"    -> {plan.path_for(fmt)}")
            if opts.summarize:
                console.print(f"    -> {plan.directory / (plan.stem + '_summary.txt')}")
        return 0

    quiet = args.quiet
    status = console.status("") if not quiet else None
    spinning = False

    def on_progress(stage: str, message: str) -> None:
        # Whisper draws its own progress bar with an ETA, which is more useful
        # than a spinner. Step aside for it rather than redrawing over it.
        nonlocal spinning
        if not status:
            return
        if stage == "transcribe":
            if spinning:
                status.stop()
                spinning = False
            console.print(f"[cyan]{message}[/cyan]")
        else:
            if not spinning:
                status.start()
                spinning = True
            status.update(f"[cyan]{message}[/cyan]")

    def on_model_load(size: str) -> None:
        nonlocal spinning
        if status and not spinning:
            status.start()
            spinning = True
        if status:
            status.update(f"[cyan]loading model '{size}'[/cyan]")

    try:
        results = run_jobs(sources, opts, on_progress, on_model_load)
    finally:
        if status and spinning:
            status.stop()

    return _report(results, quiet)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run. Returns an exit code."""
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    return run(args)
