"""
Where output goes.

One rule set, used by both the TUI and the CLI, so results land somewhere the
user is already working instead of always in the project's transcripts/ folder.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src import config


@dataclass
class OutputPlan:
    """The directory and stem that every output format is written under."""

    directory: Path
    stem: str

    def path_for(self, fmt: str) -> Path:
        """Return the output path for one format, e.g. 'md' -> <dir>/<stem>.md."""
        return self.directory / f"{self.stem}.{fmt}"


def is_inside(path: Path, parent: Path) -> bool:
    """Check whether path lives under parent."""
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _looks_like_directory(explicit: Path) -> bool:
    """Decide whether an -o value names a directory rather than a file."""
    if explicit.is_dir():
        return True
    if str(explicit).endswith(("/", "\\")):
        return True
    return not explicit.suffix


def plan_output(
    source: Path,
    explicit: Optional[Path] = None,
    input_dir: Path = config.DEFAULT_INPUT_DIR,
    output_dir: Path = config.DEFAULT_OUTPUT_DIR,
) -> OutputPlan:
    """
    Decide where a job's outputs are written.

    Priority: an explicit -o wins; otherwise files taken from the project's
    audio library keep landing in transcripts/; everything else is written
    next to the file it came from, so there is nothing to copy back.

    @source: The original input the user named, not a cached extraction.
    @explicit: An -o value, either a directory or a file path.
    @input_dir: The project's audio library.
    @output_dir: The project's transcript directory.
    @return: OutputPlan giving the directory and stem for all formats.
    """
    if explicit is not None:
        if _looks_like_directory(explicit):
            return OutputPlan(directory=explicit, stem=source.stem)
        return OutputPlan(directory=explicit.parent, stem=explicit.stem)

    if is_inside(source, input_dir):
        return OutputPlan(directory=output_dir, stem=source.stem)

    return OutputPlan(directory=source.parent, stem=source.stem)


def collect_media(paths: list[Path]) -> list[Path]:
    """
    Expand a list of files and directories into media files.

    Directories are scanned one level deep. Non-media files are dropped.

    @paths: Files and/or directories named by the user.
    @return: Sorted, de-duplicated media file paths.
    """
    from src.media import is_media  # pylint: disable=import-outside-toplevel

    found: list[Path] = []
    for p in paths:
        if p.is_dir():
            found.extend(f for f in sorted(p.iterdir()) if f.is_file() and is_media(f))
        elif p.is_file():
            found.append(p)
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in found:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(f)
    return unique
