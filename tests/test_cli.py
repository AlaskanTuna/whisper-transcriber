"""Argument parsing and headless dispatch."""

import pytest

from src import config
from src.cli import build_parser, parse_formats


class TestParseFormats:
    def test_default_when_nothing_requested(self):
        assert parse_formats(None, polish=False) == [config.DEFAULT_OUTPUT_FORMAT]

    def test_comma_separated(self):
        assert parse_formats(["txt,srt"], polish=False) == ["txt", "srt"]

    def test_repeated_flags(self):
        assert parse_formats(["txt", "srt"], polish=False) == ["txt", "srt"]

    def test_all_expands_to_every_format(self):
        assert parse_formats(["all"], polish=False) == config.OUTPUT_FORMATS

    def test_polish_flag_adds_markdown(self):
        assert config.POLISHED_FORMAT in parse_formats(None, polish=True)

    def test_markdown_always_brings_the_raw_transcript_along(self):
        # The polished document is derived from the transcript; keeping the txt
        # means a polish failure never leaves the user with nothing.
        assert parse_formats(["md"], polish=False) == ["txt", "md"]

    def test_deduplicates(self):
        assert parse_formats(["txt,txt", "txt"], polish=False) == ["txt"]

    def test_case_insensitive(self):
        assert parse_formats(["MD"], polish=False) == ["txt", "md"]

    def test_unknown_format_names_the_valid_ones(self):
        with pytest.raises(ValueError, match="Unknown format"):
            parse_formats(["docx"], polish=False)


class TestParser:
    def test_no_arguments_yields_no_inputs(self):
        args = build_parser().parse_args([])
        assert args.inputs == []

    def test_paths_and_output(self, tmp_path):
        args = build_parser().parse_args(["a.mp4", "b.mp3", "-o", str(tmp_path)])
        assert [p.name for p in args.inputs] == ["a.mp4", "b.mp3"]
        assert args.output == tmp_path

    def test_defaults_come_from_config(self):
        args = build_parser().parse_args(["a.mp4"])
        assert args.model == config.DEFAULT_MODEL_SIZE
        assert args.task == config.DEFAULT_TASK
        assert args.profile == config.DEFAULT_POLISH_PROFILE
        assert args.language is None

    def test_context_and_profile(self):
        args = build_parser().parse_args(
            ["a.mp4", "--polish", "--profile", "talk", "--context", "Alex Toh of TDG"]
        )
        assert args.polish and args.profile == "talk"
        assert args.context == "Alex Toh of TDG"

    def test_invalid_model_is_rejected(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["a.mp4", "-m", "gigantic"])

    def test_flags_default_off(self):
        args = build_parser().parse_args(["a.mp4"])
        assert not args.overwrite
        assert not args.summarize
        assert not args.no_keep_audio
        assert not args.dry_run


class TestRun:
    def test_dry_run_lists_outputs_without_writing_anything(self, tmp_path, capsys):
        from src.cli import run

        source = tmp_path / "clip.mp3"
        source.touch()
        args = build_parser().parse_args([str(source), "-f", "txt,srt", "--dry-run"])

        assert run(args) == 0
        out = capsys.readouterr().out
        assert "clip.txt" in out and "clip.srt" in out
        assert not (tmp_path / "clip.txt").exists()

    def test_no_media_found_is_an_error(self, tmp_path, capsys):
        from src.cli import run

        args = build_parser().parse_args([str(tmp_path / "missing.mp4")])
        assert run(args) == 1
        assert "No media files" in capsys.readouterr().out

    def test_bad_format_reports_and_exits_nonzero(self, tmp_path, capsys):
        from src.cli import run

        source = tmp_path / "clip.mp3"
        source.touch()
        args = build_parser().parse_args([str(source), "-f", "docx"])

        assert run(args) == 1
        assert "Unknown format" in capsys.readouterr().out

    def test_polish_without_an_api_key_fails_before_loading_whisper(
        self, tmp_path, capsys, monkeypatch
    ):
        import src.llm as llm
        from src.cli import run

        monkeypatch.setattr(llm, "is_available", lambda: False)
        monkeypatch.setattr(llm, "load_env", lambda: None)

        source = tmp_path / "clip.mp3"
        source.touch()
        args = build_parser().parse_args([str(source), "--polish"])

        assert run(args) == 1
        assert "GEMINI_API_KEY" in capsys.readouterr().out
