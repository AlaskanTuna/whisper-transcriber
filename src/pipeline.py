"""
The one job runner.

Both the TUI and the CLI call run_jobs(), so the two front-ends cannot drift
apart in what they actually do with a file.
"""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Optional

from src import config, formatter, media, paths
from src.llm import LLMError

# (stage, message). Stage is one of 'extract', 'transcribe', 'polish', 'summarize'.
ProgressCallback = Callable[[str, str], None]


@dataclass
class JobOptions:
    """Everything that varies between runs."""

    model_size: str = config.DEFAULT_MODEL_SIZE
    language: Optional[str] = None
    task: str = "transcribe"
    formats: list[str] = field(default_factory=lambda: [config.DEFAULT_OUTPUT_FORMAT])
    output: Optional[Path] = None
    polish_profile: str = config.DEFAULT_POLISH_PROFILE
    context: Optional[str] = None
    summarize: bool = False
    summary_style: str = "concise"
    overwrite: bool = False
    keep_audio: bool = config.KEEP_EXTRACTED_AUDIO
    audio_bitrate: str = config.DEFAULT_AUDIO_BITRATE
    audio_dir: Path = config.DEFAULT_INPUT_DIR

    @property
    def polish(self) -> bool:
        """Polishing runs exactly when a Markdown document was requested."""
        return config.POLISHED_FORMAT in self.formats


@dataclass
class JobResult:
    """What happened to one input file."""

    source: Path
    success: bool = False
    outputs: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    summary_path: Optional[Path] = None
    duration: Optional[float] = None
    extracted_audio: Optional[Path] = None


def _write_outputs(
    plan: paths.OutputPlan,
    fmts: list[str],
    segments: list[dict],
    metadata: dict,
    overwrite: bool,
    result: JobResult,
) -> None:
    """Render and write every mechanical format, honouring overwrite protection."""
    for fmt in fmts:
        target = plan.path_for(fmt)
        if target.exists() and not overwrite:
            result.skipped.append(target)
            continue
        formatter.write(fmt, target, segments, metadata)
        result.outputs.append(target)


def run_job(
    source: Path,
    model: Any,
    opts: JobOptions,
    on_progress: Optional[ProgressCallback] = None,
) -> JobResult:
    """
    Transcribe one file and write every requested output.

    @source: The input the user named -- audio or video, from anywhere on disk.
    @model: A loaded Whisper model.
    @opts: Run options.
    @on_progress: Called with short status strings for display.
    @return: JobResult describing what was written.
    """
    result = JobResult(source=source)

    def say(stage: str, message: str) -> None:
        if on_progress:
            on_progress(stage, message)

    # Transcribing takes minutes; if every output already exists and we are not
    # allowed to replace them, there is nothing to do.
    plan = paths.plan_output(source, opts.output, opts.audio_dir, config.DEFAULT_OUTPUT_DIR)
    if not opts.overwrite:
        targets = [plan.path_for(fmt) for fmt in opts.formats]
        if opts.summarize:
            targets.append(plan.directory / f"{plan.stem}_summary.txt")
        if targets and all(t.exists() for t in targets):
            result.skipped = targets
            result.success = True
            return result

    try:
        prepared = media.prepare_audio(
            source,
            audio_dir=opts.audio_dir,
            bitrate=opts.audio_bitrate,
            keep=opts.keep_audio,
        )
    except media.MediaError as e:
        result.error = str(e)
        return result

    if prepared.extracted:
        say("extract", f"extracted audio from {source.name}")
        if opts.keep_audio:
            result.extracted_audio = prepared.path

    try:
        info = media.probe(prepared.path)
        result.duration = info.duration
    except media.MediaError:
        result.duration = None

    try:
        from src.transcriber import transcribe  # pylint: disable=import-outside-toplevel

        say("transcribe", f"transcribing {source.name}")
        whisper_result = transcribe(model, prepared.path, opts.language, opts.task)
    except Exception as e:  # pylint: disable=broad-exception-caught
        result.error = str(e)
        return result
    finally:
        prepared.cleanup()

    segments = whisper_result.get("segments") or []
    detected = whisper_result.get("language") or opts.language

    plan.directory.mkdir(parents=True, exist_ok=True)

    metadata = {
        "source_name": source.name,
        "model": opts.model_size,
        "language": detected,
        "duration": result.duration,
        "task": opts.task,
        "generated": date.today().isoformat(),
    }

    mechanical = [f for f in opts.formats if f != config.POLISHED_FORMAT]
    _write_outputs(plan, mechanical, segments, metadata, opts.overwrite, result)

    if opts.polish:
        target = plan.path_for(config.POLISHED_FORMAT)
        if target.exists() and not opts.overwrite:
            result.skipped.append(target)
        else:
            try:
                from src.polish import polish  # pylint: disable=import-outside-toplevel
                from src.transcriber import get_device  # pylint: disable=import-outside-toplevel

                say("polish", f"structuring {source.name}")
                polish_meta = {
                    **metadata,
                    "device": get_device(),
                    "gemini_model": config.GEMINI_MODEL,
                    "raw_name": plan.path_for("txt").name,
                }
                polished = polish(
                    segments,
                    polish_meta,
                    profile=opts.polish_profile,
                    context=opts.context,
                    on_progress=lambda d, t, label: say("polish", f"structuring {label}"),
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(polished.markdown, encoding="utf-8")
                result.outputs.append(target)
                result.warnings.extend(polished.errors)
            except LLMError as e:
                result.warnings.append(f"polish failed: {e}")

    if opts.summarize:
        try:
            from src.summarizer import summarize_text  # pylint: disable=import-outside-toplevel

            say("summarize", f"summarizing {source.name}")
            summary = summarize_text(formatter.render_txt(segments), opts.summary_style)
            summary_path = plan.directory / f"{plan.stem}_summary.txt"
            summary_path.write_text(summary, encoding="utf-8")
            result.summary_path = summary_path
            result.outputs.append(summary_path)
        except LLMError as e:
            result.warnings.append(f"summary failed: {e}")

    result.success = True
    return result


def run_jobs(
    sources: list[Path],
    opts: JobOptions,
    on_progress: Optional[ProgressCallback] = None,
    on_model_load: Optional[Callable[[str], None]] = None,
) -> list[JobResult]:
    """
    Run every source through the pipeline, loading the Whisper model once.

    @sources: Input files.
    @opts: Run options, applied to all sources.
    @on_progress: Called with short status strings.
    @on_model_load: Called once before the model loads.
    @return: One JobResult per source, in order.
    """
    if not sources:
        return []

    from src.transcriber import load_model  # pylint: disable=import-outside-toplevel

    if on_model_load:
        on_model_load(opts.model_size)
    model = load_model(opts.model_size)

    return [run_job(source, model, opts, on_progress) for source in sources]
