"""
Turning a raw transcript into a structured document.

Two passes. Pass A walks the recording in overlapping windows and rewrites each
into Markdown sections, carrying forward the names and spellings established so
far so later windows stay consistent with earlier ones. Pass B reads the
assembled body once and writes the front matter and closing section.

Polishing is additive: the raw transcript is always written first and a failure
here never costs the user their transcription.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Optional

from src import config, prompts
from src.formatter import format_timestamp, render_txt
from src.llm import LLMError, generate

# Window sizes chosen so a chunk stays well inside the model's useful context
# while still giving it enough material to find topic boundaries.
WINDOW_SECONDS = 720
OVERLAP_SECONDS = 30

ProgressCallback = Callable[[int, int, str], None]


@dataclass
class Chunk:
    """One window of the recording, plus the overlap that precedes it."""

    segments: list[dict]
    start: float
    end: float
    has_overlap: bool


@dataclass
class PolishResult:
    """The finished document and anything that went wrong producing it."""

    markdown: str
    errors: list[str] = field(default_factory=list)
    chunks: int = 0


def chunk_segments(
    segments: list[dict],
    window: int = WINDOW_SECONDS,
    overlap: int = OVERLAP_SECONDS,
) -> list[Chunk]:
    """
    Split segments into fixed time windows, each preceded by a short overlap.

    @segments: Whisper segment dicts, in order.
    @window: Window length in seconds.
    @overlap: Seconds of preceding material included as context.
    @return: Chunks covering the whole recording.
    """
    if not segments:
        return []

    first = segments[0]["start"]
    last = segments[-1]["end"]
    chunks: list[Chunk] = []

    start = first
    while start < last:
        stop = start + window
        context_start = max(first, start - overlap)
        body = [s for s in segments if context_start <= s["start"] < stop]
        if body:
            chunks.append(
                Chunk(
                    segments=body,
                    start=start,
                    end=min(stop, last),
                    has_overlap=context_start < start,
                )
            )
        start = stop

    return chunks


def slugify(heading: str) -> str:
    """
    Build a GitHub-compatible anchor from a heading.

    Punctuation and emoji are dropped, then spaces become hyphens -- matching
    how GitHub and most Markdown renderers generate heading anchors.
    """
    text = heading.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    # Each remaining space becomes its own hyphen, so "A — B" yields "a--b" the
    # way GitHub renders it. Collapsing them here would break every anchor.
    return re.sub(r"\s", "-", text.strip())


def short_time(seconds: float, long_form: bool) -> str:
    """Render a section timestamp as HH:MM for long recordings, MM:SS otherwise."""
    total = int(max(0.0, seconds))
    if long_form:
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}"
    return f"{total // 60:02d}:{total % 60:02d}"


def _parse_timestamp(stamp: str) -> float:
    """Parse HH:MM:SS(.mmm) or MM:SS into seconds; unparseable input yields 0."""
    parts = stamp.strip().strip("[]").split(":")
    try:
        values = [float(p) for p in parts]
    except ValueError:
        return 0.0
    seconds = 0.0
    for value in values:
        seconds = seconds * 60 + value
    return seconds


def _merge(existing: list[dict], incoming: list[dict], key: str) -> list[dict]:
    """Append items whose key is not already present, preserving first-seen order."""
    seen = {item[key].strip().lower() for item in existing if item.get(key)}
    for item in incoming or []:
        value = (item.get(key) or "").strip()
        if value and value.lower() not in seen:
            seen.add(value.lower())
            existing.append(item)
    return existing


# A generated table whose separator row sits mid-line means the model flattened
# it; a speaker turn on the line above another merges both into one paragraph.
_TABLE_SEPARATOR = re.compile(r"\|\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|")
_TURN_START = re.compile(r"^\*\*\[\d{1,2}:\d{2}(?::\d{2})?[^\]]*\]")


def _unflatten_tables(text: str) -> str:
    """Put a table that was emitted on a single line back onto separate rows."""
    out: list[str] = []
    for line in text.split("\n"):
        if not _TABLE_SEPARATOR.search(line):
            out.append(line)
            continue
        if not line.lstrip().startswith("|"):
            head, _, rest = line.partition("|")
            if head.strip():
                out.extend([head.rstrip(), ""])
            line = "|" + rest
        # Rows were joined end-pipe to start-pipe; split them back apart.
        out.extend(re.sub(r"\|\s+\|", "|\n|", line).split("\n"))
    return "\n".join(out)


def _space_turns(text: str) -> str:
    """Ensure a blank line before each speaker turn so they stay separate paragraphs."""
    out: list[str] = []
    for line in text.split("\n"):
        if _TURN_START.match(line.strip()) and out and out[-1].strip():
            out.append("")
        out.append(line)
    return "\n".join(out)


def normalize_markdown(text: str) -> str:
    """
    Repair the Markdown mistakes the model reliably makes.

    Models flatten tables onto one line and run speaker turns together; both
    render as garbage. Cheaper and more dependable to fix here than to keep
    asking the prompt more firmly.
    """
    text = _unflatten_tables(text)
    text = _space_turns(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a Markdown table."""
    head = "| " + " | ".join(headers) + " |"
    rule = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return f"{head}\n{rule}\n{body}"


def _method_block(meta: dict) -> str:
    """Build the source/method/editing blockquote that opens the document."""
    duration = meta.get("duration")
    length = f" ({format_timestamp(duration, milliseconds=False)})" if duration else ""
    language = meta.get("language") or "auto-detected"
    lines = [
        f"> **Source** — `{meta.get('source_name', 'unknown')}`{length}. "
        f"**Method** — transcribed with OpenAI Whisper (`{meta.get('model', '?')}`, "
        f"`language={language}`) on {meta.get('device', 'CPU')}; structured with "
        f"Gemini (`{meta.get('gemini_model', config.GEMINI_MODEL)}`).",
        "> **Editing** — timestamps preserved; filler and repetition trimmed; ASR-mangled "
        "proper nouns corrected (see key below). Speaker attribution is inferred from "
        "content — Whisper does not identify speakers.",
        f"> **Generated** — {meta.get('generated', date.today().isoformat())}. "
        f"Raw transcript: `{meta.get('raw_name', 'n/a')}`.",
    ]
    return "\n".join(lines)


def assemble(front: dict, sections: list[dict], meta: dict) -> str:
    """
    Build the final Markdown document from front matter and body sections.

    @front: Pass B output (title, overview, participants, corrections, closing).
    @sections: Pass A sections, each with 'seconds', 'title' and 'body'.
    @meta: Run metadata for the method blockquote.
    @return: The complete Markdown document.
    """
    long_form = bool(meta.get("duration") and meta["duration"] >= 3600)
    parts: list[str] = [f"# {front.get('title') or 'Transcript'}", "", _method_block(meta), ""]

    overview = (front.get("overview") or "").strip()
    if overview:
        parts += [overview, ""]

    participants = front.get("participants") or []
    if participants:
        rows = [
            [f"**{p.get('name', '').strip()}**", (p.get("role") or "").strip() or "—"]
            for p in participants
            if p.get("name")
        ]
        if rows:
            parts += ["## Participants", "", _table(["Person", "Role"], rows), ""]

    corrections = front.get("corrections") or []
    if corrections:
        rows = [
            [f"\"{c.get('heard', '').strip()}\"", f"**{c.get('actual', '').strip()}**"]
            for c in corrections
            if c.get("heard") and c.get("actual")
        ]
        if rows:
            parts += [
                "## Proper-noun correction key",
                "",
                "Whisper mangled these; corrections are applied throughout.",
                "",
                _table(["Heard as", "Actually"], rows),
                "",
            ]

    unresolved = [u for u in (front.get("unresolved") or []) if u.strip()]
    if unresolved:
        parts += ["**Unresolved:**", ""]
        parts += [f"- {u.strip()}" for u in unresolved]
        parts += [""]

    headings: list[tuple[str, str, str]] = []
    for section in sections:
        stamp = short_time(section["seconds"], long_form)
        title = section["title"].strip()
        headings.append((stamp, title, slugify(f"{stamp} — {title}")))

    if headings:
        rows = [[f"[{stamp}](#{anchor})", title] for stamp, title, anchor in headings]
        parts += ["---", "", "## Contents", "", _table(["Time", "Segment"], rows), "", "---", ""]

    for (stamp, title, _), section in zip(headings, sections):
        parts += [f"## {stamp} — {title}", "", normalize_markdown(section["body"]), "", "---", ""]

    closing = normalize_markdown(front.get("closing") or "")
    if closing:
        parts += [f"## {front.get('closing_title') or 'Summary'}", "", closing, ""]

    return "\n".join(parts).rstrip() + "\n"


def polish(
    segments: list[dict],
    meta: dict,
    profile: str = "meeting",
    context: Optional[str] = None,
    on_progress: Optional[ProgressCallback] = None,
) -> PolishResult:
    """
    Turn raw Whisper segments into a structured Markdown document.

    @segments: Whisper segment dicts.
    @meta: Run metadata (source_name, model, language, device, duration, raw_name).
    @profile: One of 'meeting', 'talk', 'general'.
    @context: Optional known facts -- names, companies, spellings -- to anchor the ASR.
    @on_progress: Called as (done, total, label) after each model request.
    @return: PolishResult with the document and any non-fatal errors.
    """
    if not segments:
        raise LLMError("Nothing to polish: the transcript is empty")

    chunks = chunk_segments(segments)
    total = len(chunks) + 1
    errors: list[str] = []
    sections: list[dict] = []
    speakers: list[dict] = []
    corrections: list[dict] = []
    unresolved: list[str] = []

    for index, chunk in enumerate(chunks):
        start = format_timestamp(chunk.start, milliseconds=False)
        end = format_timestamp(chunk.end, milliseconds=False)
        prompt = prompts.build_body_prompt(
            chunk_text=render_txt(chunk.segments, milliseconds=False),
            start=start,
            end=end,
            profile=profile,
            context=context,
            speakers=speakers,
            corrections=corrections,
            overlap_note=chunk.has_overlap,
        )

        try:
            data = generate(prompt, schema=prompts.BODY_SCHEMA)
        except LLMError as e:
            errors.append(f"{start}-{end}: {e}")
            sections.append(
                {
                    "seconds": chunk.start,
                    "title": f"{start} (unpolished)",
                    "body": (
                        "> Structuring failed for this portion; the raw transcript is "
                        "reproduced below.\n\n"
                        + render_txt(
                            [s for s in chunk.segments if s["start"] >= chunk.start],
                            milliseconds=False,
                        )
                    ),
                }
            )
        else:
            for section in data.get("sections") or []:
                body = (section.get("body") or "").strip()
                if not body:
                    continue
                sections.append(
                    {
                        "seconds": _parse_timestamp(section.get("timestamp", "")),
                        "title": (section.get("title") or "Untitled").strip(),
                        "body": body,
                    }
                )
            _merge(speakers, data.get("speakers") or [], "name")
            _merge(corrections, data.get("corrections") or [], "heard")
            unresolved.extend(u for u in (data.get("unresolved") or []) if u.strip())

        if on_progress:
            on_progress(index + 1, total, f"section {index + 1}/{len(chunks)}")

    sections.sort(key=lambda s: s["seconds"])
    body_markdown = "\n\n".join(
        f"## {format_timestamp(s['seconds'], milliseconds=False)} — {s['title']}\n\n{s['body']}"
        for s in sections
    )

    front: dict = {}
    try:
        front = generate(
            prompts.build_front_prompt(
                body=body_markdown,
                profile=profile,
                context=context,
                speakers=speakers,
                corrections=corrections,
                unresolved=unresolved,
            ),
            schema=prompts.FRONT_SCHEMA,
        )
    except LLMError as e:
        errors.append(f"front matter: {e}")
        front = {
            "title": Path(meta.get("source_name", "Transcript")).stem,
            "overview": "",
            "participants": speakers,
            "corrections": corrections,
            "unresolved": unresolved,
            "closing_title": "",
            "closing": "",
        }
    else:
        _merge(front.setdefault("participants", []), speakers, "name")
        _merge(front.setdefault("corrections", []), corrections, "heard")

    if on_progress:
        on_progress(total, total, "front matter")

    return PolishResult(markdown=assemble(front, sections, meta), errors=errors, chunks=len(chunks))
