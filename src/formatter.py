"""
Rendering Whisper segments into output formats.

Pure functions over the segment list Whisper returns. No I/O beyond write().
"""

import json
from pathlib import Path

# Segments are Whisper's dicts: {'start': float, 'end': float, 'text': str}
Segment = dict


def format_timestamp(seconds: float, separator: str = ".", milliseconds: bool = True) -> str:
    """
    Format a second offset as HH:MM:SS with optional milliseconds.

    @seconds: Offset in seconds; negatives are clamped to zero.
    @separator: Character between seconds and milliseconds ('.' or ',').
    @milliseconds: Whether to include the millisecond component.
    @return: Formatted timestamp string.
    """
    seconds = max(0.0, float(seconds))
    total = int(seconds)
    ms = int(round((seconds - total) * 1000))
    if ms == 1000:  # rounding pushed us into the next second
        total += 1
        ms = 0
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    stamp = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{stamp}{separator}{ms:03d}" if milliseconds else stamp


def render_txt(segments: list[Segment], milliseconds: bool = True) -> str:
    """
    Render the timestamped plain-text transcript.

    @segments: Whisper segment dicts.
    @milliseconds: Whether timestamps carry a millisecond component. The polish
        pass asks for False so the model copies clean [HH:MM:SS] stamps into its
        speaker turns instead of the noisier full-precision ones.
    @return: One blank-line-separated turn per segment.
    """
    lines = [
        f"[{format_timestamp(s['start'], milliseconds=milliseconds)}] {s['text'].strip()}"
        for s in segments
        if s.get("text", "").strip()
    ]
    return "\n\n".join(lines) + "\n" if lines else ""


def render_srt(segments: list[Segment]) -> str:
    """Render SubRip subtitles."""
    blocks = []
    index = 1
    for s in segments:
        text = s.get("text", "").strip()
        if not text:
            continue
        start = format_timestamp(s["start"], separator=",")
        end = format_timestamp(s["end"], separator=",")
        blocks.append(f"{index}\n{start} --> {end}\n{text}\n")
        index += 1
    return "\n".join(blocks)


def render_vtt(segments: list[Segment]) -> str:
    """Render WebVTT subtitles."""
    blocks = ["WEBVTT\n"]
    for s in segments:
        text = s.get("text", "").strip()
        if not text:
            continue
        start = format_timestamp(s["start"])
        end = format_timestamp(s["end"])
        blocks.append(f"{start} --> {end}\n{text}\n")
    return "\n".join(blocks)


def render_json(segments: list[Segment], metadata: dict | None = None) -> str:
    """Render segments plus optional run metadata as indented JSON."""
    payload = {
        "metadata": metadata or {},
        "segments": [
            {
                "start": s["start"],
                "end": s["end"],
                "text": s.get("text", "").strip(),
            }
            for s in segments
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


_RENDERERS = {
    "txt": render_txt,
    "srt": render_srt,
    "vtt": render_vtt,
}


def render(fmt: str, segments: list[Segment], metadata: dict | None = None) -> str:
    """
    Render segments in the named format.

    @fmt: One of 'txt', 'srt', 'vtt', 'json'.
    @segments: Whisper segment dicts.
    @metadata: Run metadata, used by the json format only.
    @return: The rendered document.
    """
    if fmt == "json":
        return render_json(segments, metadata)
    if fmt not in _RENDERERS:
        raise ValueError(f"Unknown format '{fmt}'")
    return _RENDERERS[fmt](segments)


def write(fmt: str, path: Path, segments: list[Segment], metadata: dict | None = None) -> Path:
    """Render segments and write them to path, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(fmt, segments, metadata), encoding="utf-8")
    return path
