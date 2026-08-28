"""The polish pipeline, with Gemini mocked out entirely."""

import pytest

from src import polish, prompts
from src.llm import LLMError


class TestChunkSegments:
    def test_short_recording_is_one_chunk(self, segments):
        chunks = polish.chunk_segments(segments)
        assert len(chunks) == 1
        assert not chunks[0].has_overlap

    def test_empty_input(self):
        assert polish.chunk_segments([]) == []

    def test_thirty_minutes_splits_into_windows(self, long_segments):
        chunks = polish.chunk_segments(long_segments, window=720, overlap=30)
        assert len(chunks) == 3
        assert [int(c.start) for c in chunks] == [0, 720, 1440]

    def test_later_chunks_carry_preceding_overlap(self, long_segments):
        chunks = polish.chunk_segments(long_segments, window=720, overlap=30)
        assert chunks[1].has_overlap
        # The overlap reaches back before the window start, for continuity.
        assert chunks[1].segments[0]["start"] < chunks[1].start

    def test_every_segment_appears_at_least_once(self, long_segments):
        chunks = polish.chunk_segments(long_segments, window=720, overlap=30)
        covered = {s["start"] for c in chunks for s in c.segments}
        assert covered == {s["start"] for s in long_segments}

    def test_no_overlap_requested(self, long_segments):
        chunks = polish.chunk_segments(long_segments, window=720, overlap=0)
        assert not any(c.has_overlap for c in chunks)


class TestSlugify:
    def test_matches_github_double_hyphen_for_em_dashes(self):
        # GitHub maps each space to its own hyphen, so "A — B" becomes "a--b".
        # Collapsing whitespace here would silently break every anchor link.
        assert polish.slugify("00:27 — GonkaRouter & track reveal") == (
            "0027--gonkarouter--track-reveal"
        )

    def test_trailing_emoji_leaves_no_trailing_hyphen(self):
        assert polish.slugify("14:35 — Pool size ⭐") == "1435--pool-size"

    def test_lowercases_and_drops_punctuation(self):
        assert polish.slugify("Q1: What's next?") == "q1-whats-next"


class TestShortTime:
    def test_minutes_and_seconds_for_short_recordings(self):
        assert polish.short_time(725, long_form=False) == "12:05"

    def test_hours_and_minutes_for_long_recordings(self):
        assert polish.short_time(3725, long_form=True) == "01:02"


class TestParseTimestamp:
    def test_full_timestamp(self):
        assert polish._parse_timestamp("01:02:03.500") == pytest.approx(3723.5)

    def test_bracketed(self):
        assert polish._parse_timestamp("[00:00:05.000]") == pytest.approx(5.0)

    def test_minutes_and_seconds(self):
        assert polish._parse_timestamp("12:05") == pytest.approx(725.0)

    def test_garbage_returns_zero(self):
        assert polish._parse_timestamp("soon") == 0.0


class TestMerge:
    def test_appends_unseen_and_skips_duplicates(self):
        existing = [{"name": "Alex"}]
        polish._merge(existing, [{"name": "alex"}, {"name": "James"}], "name")
        assert [e["name"] for e in existing] == ["Alex", "James"]

    def test_ignores_blank_values(self):
        existing = []
        polish._merge(existing, [{"name": "  "}], "name")
        assert existing == []


class TestNormalizeMarkdown:
    def test_flattened_table_is_split_back_into_rows(self):
        # Observed real output: the model ran a whole table onto the end of a
        # sentence, which renders as literal pipe characters.
        broken = (
            "The discussion centered on the talent pool. | Question | Details | "
            "|---|---| | Sourcing | Over 17 hackathons. | | Reach | All Malaysia. |"
        )
        fixed = polish.normalize_markdown(broken)
        lines = fixed.split("\n")
        assert lines[0] == "The discussion centered on the talent pool."
        assert lines[1] == ""
        assert lines[2] == "| Question | Details |"
        assert lines[3] == "|---|---|"
        assert lines[4] == "| Sourcing | Over 17 hackathons. |"

    def test_well_formed_table_is_untouched(self):
        table = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        assert polish.normalize_markdown(table) == table

    def test_adjacent_speaker_turns_get_a_blank_line(self):
        merged = "**[00:04:11] B:** Yes.\n**[00:04:12] C:** Next question."
        assert polish.normalize_markdown(merged) == (
            "**[00:04:11] B:** Yes.\n\n**[00:04:12] C:** Next question."
        )

    def test_already_spaced_turns_are_untouched(self):
        spaced = "**[00:00:01] A:** One.\n\n**[00:00:02] B:** Two."
        assert polish.normalize_markdown(spaced) == spaced

    def test_excess_blank_lines_collapse(self):
        assert polish.normalize_markdown("a\n\n\n\nb") == "a\n\nb"

    def test_prose_without_tables_survives(self):
        prose = "A sentence with a | pipe in it, but no table."
        assert polish.normalize_markdown(prose) == prose


class TestAssemble:
    def _front(self):
        return {
            "title": "TDG × NexTalent",
            "overview": "A discovery call.",
            "participants": [{"name": "Alex Toh", "role": "TDG"}],
            "corrections": [{"heard": "TVG", "actual": "TDG"}],
            "unresolved": ["A fourth judge company was not identified."],
            "closing_title": "Where this landed",
            "closing": "Alex will regroup with HR.",
        }

    def _sections(self):
        return [
            {"seconds": 0.0, "title": "Opening", "body": "**[00:00:00] Alex:** Hello."},
            {"seconds": 725.0, "title": "Pool size", "body": "**[00:12:05] Alex:** How big?"},
        ]

    def test_document_has_every_expected_part(self):
        doc = polish.assemble(self._front(), self._sections(), {"source_name": "call.mp4"})
        for expected in [
            "# TDG × NexTalent",
            "## Participants",
            "## Proper-noun correction key",
            "**Unresolved:**",
            "## Contents",
            "## 00:00 — Opening",
            "## 12:05 — Pool size",
            "## Where this landed",
        ]:
            assert expected in doc

    def test_every_contents_link_resolves_to_a_heading(self):
        doc = polish.assemble(self._front(), self._sections(), {"source_name": "call.mp4"})
        import re

        headings = {polish.slugify(h) for h in re.findall(r"^## (.+)$", doc, re.M)}
        links = set(re.findall(r"\]\(#([^)]+)\)", doc))
        assert links and links <= headings

    def test_long_recordings_use_hour_stamps(self):
        doc = polish.assemble(
            self._front(),
            [{"seconds": 3725.0, "title": "Later", "body": "text"}],
            {"source_name": "call.mp4", "duration": 7200},
        )
        assert "## 01:02 — Later" in doc

    def test_method_block_names_the_models(self):
        doc = polish.assemble(
            self._front(),
            self._sections(),
            {"source_name": "call.mp4", "model": "small", "language": "en",
             "device": "GPU", "gemini_model": "gemini-3.5-flash-lite"},
        )
        assert "`small`" in doc and "gemini-3.5-flash-lite" in doc
        assert "Whisper does not identify speakers" in doc

    def test_optional_sections_are_omitted_when_empty(self):
        doc = polish.assemble(
            {"title": "Bare", "overview": "", "closing_title": "", "closing": ""},
            self._sections(),
            {"source_name": "x.mp3"},
        )
        assert "## Participants" not in doc
        assert "## Proper-noun correction key" not in doc


class TestPolish:
    def _body_response(self):
        return {
            "sections": [
                {"timestamp": "00:00:00", "title": "Opening", "body": "**[00:00:00] A:** Hi."}
            ],
            "speakers": [{"name": "Alex", "role": "TDG"}],
            "corrections": [{"heard": "TVG", "actual": "TDG"}],
            "unresolved": [],
        }

    def _front_response(self):
        return {
            "title": "A Call",
            "overview": "Overview.",
            "participants": [],
            "corrections": [],
            "unresolved": [],
            "closing_title": "Summary",
            "closing": "Done.",
        }

    def test_empty_transcript_raises(self):
        with pytest.raises(LLMError, match="empty"):
            polish.polish([], {})

    def test_happy_path_builds_a_document(self, monkeypatch, segments):
        calls = []

        def fake_generate(prompt, schema=None, model=None):
            calls.append(schema)
            return (
                self._body_response()
                if schema is prompts.BODY_SCHEMA
                else self._front_response()
            )

        monkeypatch.setattr(polish, "generate", fake_generate)
        result = polish.polish(segments, {"source_name": "a.mp3"})

        assert result.errors == []
        assert "# A Call" in result.markdown
        assert calls == [prompts.BODY_SCHEMA, prompts.FRONT_SCHEMA]

    def test_glossary_carries_into_later_chunks(self, monkeypatch, long_segments):
        seen_prompts = []

        def fake_generate(prompt, schema=None, model=None):
            seen_prompts.append(prompt)
            return (
                self._body_response()
                if schema is prompts.BODY_SCHEMA
                else self._front_response()
            )

        monkeypatch.setattr(polish, "generate", fake_generate)
        polish.polish(long_segments, {"source_name": "a.mp3"})

        # The first chunk cannot know anything; later chunks must be told what
        # earlier ones established, or names drift between sections.
        assert "ESTABLISHED EARLIER" not in seen_prompts[0]
        assert "ESTABLISHED EARLIER" in seen_prompts[1]
        assert "TDG" in seen_prompts[1]

    def test_a_failed_chunk_keeps_its_raw_text(self, monkeypatch, long_segments):
        def fake_generate(prompt, schema=None, model=None):
            if schema is prompts.BODY_SCHEMA and "00:12:00" in prompt:
                raise LLMError("rate limited")
            return (
                self._body_response()
                if schema is prompts.BODY_SCHEMA
                else self._front_response()
            )

        monkeypatch.setattr(polish, "generate", fake_generate)
        result = polish.polish(long_segments, {"source_name": "a.mp3"})

        assert any("rate limited" in e for e in result.errors)
        assert "unpolished" in result.markdown
        assert "line 24" in result.markdown  # the raw content survived

    def test_front_matter_failure_still_returns_a_document(self, monkeypatch, segments):
        def fake_generate(prompt, schema=None, model=None):
            if schema is prompts.FRONT_SCHEMA:
                raise LLMError("quota exhausted")
            return self._body_response()

        monkeypatch.setattr(polish, "generate", fake_generate)
        result = polish.polish(segments, {"source_name": "recording.mp3"})

        assert any("quota exhausted" in e for e in result.errors)
        assert "## 00:00 — Opening" in result.markdown

    def test_progress_is_reported_once_per_chunk_plus_front_matter(
        self, monkeypatch, long_segments
    ):
        monkeypatch.setattr(
            polish, "generate",
            lambda p, schema=None, model=None: (
                self._body_response() if schema is prompts.BODY_SCHEMA
                else self._front_response()
            ),
        )
        seen = []
        polish.polish(long_segments, {}, on_progress=lambda d, t, label: seen.append((d, t)))

        assert seen[-1] == (4, 4)  # 3 chunks + front matter
