"""
Prompts for the polish pipeline.

Kept apart from the pipeline logic so the wording can be tuned without touching
control flow. Every prompt carries the same anti-fabrication rules.
"""

# ─── Profile guidance ────────────────────────────────────────────────────────

_PROFILE_BODY = {
    "meeting": (
        "This is a meeting or call between people who mostly know why they are there. "
        "Attribute every turn to a speaker. Track who asks for what, who commits to what, "
        "and any figure, price, date or deadline that is stated out loud."
    ),
    "talk": (
        "This is a talk, lecture, workshop or presentation with one main speaker and "
        "possibly questions from an audience. Organise by topic rather than by turn. "
        "Preserve the speaker's own phrasing for claims, definitions and recommendations."
    ),
    "general": (
        "Organise the material by topic. Attribute turns to speakers where the audio "
        "clearly has more than one, otherwise write it as continuous prose."
    ),
}

_PROFILE_CLOSING = {
    "meeting": (
        "Cover, using only what was actually said: the figures stated on the call; "
        "what each side asked for; what was agreed, committed to or explicitly deferred; "
        "and what remains open, with who owns it."
    ),
    "talk": (
        "Cover, using only what was actually said: the main claims made; the concrete "
        "recommendations given; and anything the speaker flagged as a caveat or an open question."
    ),
    "general": (
        "Cover the key points, any decisions or conclusions reached, and anything "
        "left unresolved."
    ),
}

# ─── Shared rules ────────────────────────────────────────────────────────────

_RULES = """\
RULES -- these are correctness requirements, not style preferences:

- Never invent content. Every statement in your output must be traceable to the
  transcript in front of you. If it is not there, it does not go in.
- Preserve timestamps exactly as given. Never shift, round or invent one.
- Where the audio is unintelligible, write [unclear]. Do not guess at meaning.
- Whisper does not identify speakers; you are inferring them from content. A
  confidently wrong name is worse than an honest "Speaker A" -- attach a name only
  where the transcript itself supplies the evidence: someone is addressed by name,
  introduces themselves, states their role, or speaks for a named company. A name
  appearing in the known facts is NOT on its own evidence that a given turn belongs
  to that person; you still have to find them in the transcript. Where you cannot,
  use "Speaker A", "Speaker B" and stay consistent.
- Trim filler, stammers, repetition and false starts, and merge fragmented segments
  into readable turns. "we don't we don't restrict to like a university" becomes
  "we don't restrict to a university". Do NOT paraphrase away substance, hedging or
  qualifications -- "a few only" must not become "several".
- Restore sentence case and punctuation. The recogniser often returns lowercase,
  unpunctuated runs; the finished document must read as properly written prose from
  the first section to the last. Apply this to EVERY section, including the final
  ones -- consistency across the whole document matters as much as within a section.
- Write timestamps as [HH:MM:SS], seconds precision, exactly as they appear in the
  portion you are given.
- Markdown must be real Markdown: a blank line between every speaker turn and every
  paragraph, and a table starting on its own line with each row on its own line.
  Never run a table onto the end of a sentence.
- Numbers, prices, dates, company names and personal names are load-bearing.
  Reproduce them exactly. Where the ASR clearly mangled one and context makes the
  real value certain, correct it and record it under `corrections`.
- When a sentence is worth having verbatim, keep it verbatim -- in italics inline,
  or as a blockquote when it runs long."""


def _context_block(context: str | None) -> str:
    if not context:
        return ""
    return (
        "\nKNOWN FACTS supplied by the user. Treat these spellings and names as "
        f"authoritative and correct the ASR against them:\n{context.strip()}\n"
    )


def _glossary_block(speakers: list[dict], corrections: list[dict]) -> str:
    if not speakers and not corrections:
        return ""
    lines = ["\nESTABLISHED EARLIER in this same recording -- stay consistent with these:"]
    if speakers:
        who = ", ".join(
            f"{s['name']}" + (f" ({s['role']})" if s.get("role") else "")
            for s in speakers
        )
        lines.append(f"Speakers: {who}")
    if corrections:
        fixes = ", ".join(f"\"{c['heard']}\" -> {c['actual']}" for c in corrections)
        lines.append(f"Name corrections already applied: {fixes}")
    return "\n".join(lines) + "\n"


# ─── Pass A: body sections, one chunk at a time ──────────────────────────────

BODY_SCHEMA = {
    "type": "object",
    "properties": {
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "timestamp": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["timestamp", "title", "body"],
            },
        },
        "speakers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                },
                "required": ["name"],
            },
        },
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heard": {"type": "string"},
                    "actual": {"type": "string"},
                },
                "required": ["heard", "actual"],
            },
        },
        "unresolved": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["sections"],
}


def build_body_prompt(
    chunk_text: str,
    start: str,
    end: str,
    profile: str,
    context: str | None,
    speakers: list[dict],
    corrections: list[dict],
    overlap_note: bool,
) -> str:
    """
    Build the prompt that turns one chunk of raw transcript into Markdown sections.

    @chunk_text: The raw timestamped transcript for this chunk.
    @start: Chunk start timestamp, HH:MM:SS.
    @end: Chunk end timestamp, HH:MM:SS.
    @profile: One of 'meeting', 'talk', 'general'.
    @context: Optional user-supplied known facts.
    @speakers: Speakers established by earlier chunks.
    @corrections: Corrections established by earlier chunks.
    @overlap_note: Whether this chunk opens with overlapping context.
    @return: The full prompt string.
    """
    guidance = _PROFILE_BODY.get(profile, _PROFILE_BODY["general"])
    overlap = (
        "\nThe opening of this portion overlaps the previous portion and is given for "
        "continuity only. Do not create a section for material already covered before "
        f"{start}.\n"
        if overlap_note
        else ""
    )

    return f"""\
You are turning raw speech-to-text output into a clean, faithful record of what was
said. The recogniser is Whisper: it mangles proper nouns, punctuates poorly, and does
not identify speakers.

{guidance}
{_context_block(context)}{_glossary_block(speakers, corrections)}{overlap}
{_RULES}

OUTPUT
Split this portion into 1-5 topical sections. For each section give:
- `timestamp`: HH:MM:SS where the section starts, taken from the transcript
- `title`: 3-8 words, specific to what is actually discussed
- `body`: Markdown. Write speaker turns as `**[HH:MM:SS] Name:** text`. Use tables for
  structured data such as prices, schedules or itemised lists; bullets for
  enumerations; blockquotes for extended verbatim passages.

Also report:
- `speakers`: everyone you identified here, with their role where it was stated
- `corrections`: ASR manglings you fixed, as heard -> actual, only where you are
  confident from context
- `unresolved`: anything you could not pin down -- a name, an unintelligible passage

TRANSCRIPT PORTION ({start} - {end}):
{chunk_text}"""


# ─── Pass B: front matter and closing, over the assembled body ───────────────

FRONT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "overview": {"type": "string"},
        "participants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                },
                "required": ["name"],
            },
        },
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heard": {"type": "string"},
                    "actual": {"type": "string"},
                },
                "required": ["heard", "actual"],
            },
        },
        "unresolved": {"type": "array", "items": {"type": "string"}},
        "closing_title": {"type": "string"},
        "closing": {"type": "string"},
    },
    "required": ["title", "overview", "closing_title", "closing"],
}


def build_front_prompt(
    body: str,
    profile: str,
    context: str | None,
    speakers: list[dict],
    corrections: list[dict],
    unresolved: list[str],
) -> str:
    """
    Build the prompt that produces the document's front matter and closing section.

    @body: The assembled Markdown body from pass A.
    @profile: One of 'meeting', 'talk', 'general'.
    @context: Optional user-supplied known facts.
    @speakers: Speakers gathered across all chunks.
    @corrections: Corrections gathered across all chunks.
    @unresolved: Unresolved items gathered across all chunks.
    @return: The full prompt string.
    """
    closing_guidance = _PROFILE_CLOSING.get(profile, _PROFILE_CLOSING["general"])
    gathered = _glossary_block(speakers, corrections)
    open_items = (
        "\nUnresolved items noted while transcribing:\n"
        + "\n".join(f"- {u}" for u in unresolved)
        + "\n"
        if unresolved
        else ""
    )

    return f"""\
You are finishing a transcript document. The body below has already been written from
the raw recording. Produce the front matter and a closing section for it.

{_context_block(context)}{gathered}{open_items}
{_RULES}

PRODUCE
- `title`: a short, specific name for this recording. A noun phrase, not a sentence.
  Name the actual parties or subject where they are known.
- `overview`: two or three sentences saying what this recording is and what happened
  in it. Plain statement of fact, no salesmanship.
- `participants`: everyone who speaks or is clearly present, with their role and
  affiliation where stated. Merge duplicates and inconsistent spellings.
- `corrections`: the merged, de-duplicated proper-noun correction key for the whole
  recording. Drop anything speculative.
- `unresolved`: things that stayed genuinely uncertain, phrased so a reader knows
  what to double-check. Include the timestamp where relevant.
- `closing_title`: a heading for the closing section, 2-5 words.
- `closing`: a Markdown section. {closing_guidance}
  Use tables where the content is tabular. Do not repeat the body at length; this is
  what a reader needs to take away, grounded in what was said.

DOCUMENT BODY:
{body}"""
