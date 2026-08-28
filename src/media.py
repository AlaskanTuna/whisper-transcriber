"""
Media inspection and audio extraction.

Lets the tool accept any audio or video file from anywhere on disk. Video is
converted to MP3 with ffmpeg before Whisper sees it; audio is passed straight
through. Nothing here knows about the TUI or the CLI.
"""

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src import config


class MediaError(RuntimeError):
    """Raised when a media file cannot be probed or converted."""


@dataclass
class MediaInfo:
    """What ffprobe could tell us about a file."""

    path: Path
    duration: Optional[float]
    has_audio: bool
    has_video: bool


@dataclass
class PreparedAudio:
    """An audio file ready for Whisper, plus how it came to exist."""

    path: Path
    source: Path
    extracted: bool = False
    temporary: bool = False

    def cleanup(self) -> None:
        """Delete the audio file if it was a throwaway extraction."""
        if self.temporary:
            self.path.unlink(missing_ok=True)


def ffmpeg_available() -> bool:
    """Check whether ffmpeg and ffprobe are both on PATH."""
    return bool(shutil.which("ffmpeg")) and bool(shutil.which("ffprobe"))


def is_audio(path: Path) -> bool:
    """Check whether a path has a known audio extension."""
    return path.suffix.lower() in {e.lower() for e in config.FILE_EXTENSIONS}


def is_video(path: Path) -> bool:
    """Check whether a path has a known video extension."""
    return path.suffix.lower() in {e.lower() for e in config.VIDEO_EXTENSIONS}


def is_media(path: Path) -> bool:
    """Check whether a path is a media file this tool can handle."""
    return is_audio(path) or is_video(path)


def probe(path: Path) -> MediaInfo:
    """
    Inspect a media file with ffprobe.

    @path: Path to the media file.
    @return: MediaInfo with duration and stream presence.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-show_entries", "stream=codec_type",
        "-of", "json", str(path),
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        data = json.loads(out)
    except FileNotFoundError as e:
        raise MediaError("ffprobe not found -- install ffmpeg") from e
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        raise MediaError(f"Could not read '{path.name}': not a valid media file") from e

    codec_types = {s.get("codec_type") for s in data.get("streams", [])}
    raw_duration = data.get("format", {}).get("duration")
    try:
        duration = float(raw_duration) if raw_duration is not None else None
    except (TypeError, ValueError):
        duration = None

    return MediaInfo(
        path=path,
        duration=duration,
        has_audio="audio" in codec_types,
        has_video="video" in codec_types,
    )


def build_extract_command(source: Path, dest: Path, bitrate: str) -> list[str]:
    """
    Build the ffmpeg command that extracts audio to MP3.

    @source: Input media file.
    @dest: Output .mp3 path.
    @bitrate: Encoder bitrate, e.g. '192k'.
    @return: Argument list for subprocess.
    """
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
        "-i", str(source),
        "-vn", "-acodec", "libmp3lame", "-b:a", bitrate,
        "-y", str(dest),
    ]


def extract_audio(source: Path, dest: Path, bitrate: str) -> Path:
    """
    Extract the audio track of a media file to MP3.

    @source: Input media file.
    @dest: Output .mp3 path; parent directories are created.
    @bitrate: Encoder bitrate, e.g. '192k'.
    @return: The destination path.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_extract_command(source, dest, bitrate)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as e:
        raise MediaError("ffmpeg not found -- install ffmpeg") from e

    if proc.returncode != 0 or not dest.exists():
        detail = (proc.stderr or "").strip().splitlines()
        message = detail[-1] if detail else f"exit code {proc.returncode}"
        raise MediaError(f"Audio extraction failed for '{source.name}': {message}")

    return dest


def _cache_is_fresh(source: Path, cached: Path) -> bool:
    """Check whether a cached extraction is present and newer than its source."""
    return (
        cached.exists()
        and cached.stat().st_size > 0
        and cached.stat().st_mtime >= source.stat().st_mtime
    )


def prepare_audio(
    source: Path,
    audio_dir: Path,
    bitrate: str = config.DEFAULT_AUDIO_BITRATE,
    keep: bool = True,
) -> PreparedAudio:
    """
    Return an audio file Whisper can read, extracting from video if needed.

    Audio input is passed through untouched. Video input is extracted to MP3 --
    cached in audio_dir under the source stem when keep is True, so a re-run
    reuses it, or to a temp file that the caller deletes when keep is False.

    @source: Any audio or video file.
    @audio_dir: Directory for kept extractions.
    @bitrate: Encoder bitrate for extraction.
    @keep: Whether to keep the extracted MP3 after the run.
    @return: PreparedAudio describing what to feed Whisper.
    """
    if not source.exists():
        raise MediaError(f"File not found: {source}")

    if is_audio(source):
        return PreparedAudio(path=source, source=source)

    if not is_video(source):
        raise MediaError(
            f"Unsupported file type '{source.suffix or 'none'}'. "
            f"Supported: {', '.join(config.MEDIA_EXTENSIONS)}"
        )

    info = probe(source)
    if not info.has_audio:
        raise MediaError(f"'{source.name}' has no audio track")

    if keep:
        dest = audio_dir / f"{source.stem}.mp3"
        if _cache_is_fresh(source, dest):
            return PreparedAudio(path=dest, source=source, extracted=True)
    else:
        handle = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        handle.close()
        dest = Path(handle.name)

    extract_audio(source, dest, bitrate)
    return PreparedAudio(path=dest, source=source, extracted=True, temporary=not keep)
