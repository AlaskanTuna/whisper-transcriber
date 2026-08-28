"""Rendering is pure, so it is tested exhaustively and cheaply."""

import json

import pytest

from src import formatter


class TestFormatTimestamp:
    def test_zero(self):
        assert formatter.format_timestamp(0) == "00:00:00.000"

    def test_milliseconds_kept(self):
        assert formatter.format_timestamp(5.639) == "00:00:05.639"

    def test_hour_rollover(self):
        assert formatter.format_timestamp(3661.5) == "01:01:01.500"

    def test_rounding_up_carries_into_the_next_second(self):
        # 3599.9996 rounds to 1000ms, which must become the next whole second
        # rather than an impossible "00:59:59.1000".
        assert formatter.format_timestamp(3599.9996) == "01:00:00.000"

    def test_negative_clamped(self):
        assert formatter.format_timestamp(-4) == "00:00:00.000"

    def test_comma_separator_for_srt(self):
        assert formatter.format_timestamp(1.25, separator=",") == "00:00:01,250"

    def test_without_milliseconds(self):
        assert formatter.format_timestamp(75, milliseconds=False) == "00:01:15"


class TestRenderTxt:
    def test_strips_and_separates(self, segments):
        out = formatter.render_txt(segments)
        assert out.startswith("[00:00:00.000] Hello there\n\n")
        assert out.endswith("\n")

    def test_drops_blank_segments(self):
        out = formatter.render_txt([{"start": 0, "end": 1, "text": "   "}])
        assert out == ""

    def test_empty_input(self):
        assert formatter.render_txt([]) == ""


class TestRenderSrt:
    def test_numbering_and_arrow(self, segments):
        out = formatter.render_srt(segments)
        assert out.startswith("1\n00:00:00,000 --> 00:00:02,500\nHello there\n")
        assert "\n2\n" in out

    def test_blank_segments_do_not_consume_an_index(self):
        out = formatter.render_srt([
            {"start": 0, "end": 1, "text": "a"},
            {"start": 1, "end": 2, "text": "  "},
            {"start": 2, "end": 3, "text": "b"},
        ])
        assert "3\n" not in out
        assert out.count(" --> ") == 2


class TestRenderVtt:
    def test_has_header_and_no_indices(self, segments):
        out = formatter.render_vtt(segments)
        assert out.startswith("WEBVTT\n")
        assert "\n1\n" not in out


class TestRenderJson:
    def test_roundtrips(self, segments):
        data = json.loads(formatter.render_json(segments, {"model": "small"}))
        assert data["metadata"]["model"] == "small"
        assert len(data["segments"]) == 3
        assert data["segments"][0]["text"] == "Hello there"


class TestRenderDispatch:
    @pytest.mark.parametrize("fmt", ["txt", "srt", "vtt", "json"])
    def test_every_format_renders(self, fmt, segments):
        assert formatter.render(fmt, segments)

    def test_unknown_format_raises(self, segments):
        with pytest.raises(ValueError, match="Unknown format"):
            formatter.render("docx", segments)

    def test_write_creates_parent_directories(self, tmp_path, segments):
        target = tmp_path / "deep" / "nested" / "out.txt"
        formatter.write("txt", target, segments)
        assert target.read_text(encoding="utf-8").startswith("[00:00:00.000]")
